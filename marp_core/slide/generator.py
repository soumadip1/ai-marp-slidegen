"""
Slide plan generation using GPT-5.4-mini.

Generates complete slide plans from presentation topics.
"""

import json
import re
from importlib import resources
from typing import Any

from openai import OpenAI

from ..config import OPENAI_API_KEY
from ..utils.text import sanitize_text
from ..utils.validators import is_valid_mermaid
from .diagram_optimizer import optimize_diagram_placement


def _get_client() -> OpenAI:
    """
    Create an OpenAI client only when generation is requested.
    """
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set. Add it to your environment or .env file.")
    return OpenAI(api_key=OPENAI_API_KEY)


def _safe_message_text(response: Any) -> str:
    """
    Return text content from an OpenAI chat completion response.
    """
    message = response.choices[0].message
    content = message.content

    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    # Defensive fallback for SDK/content variants where content can be structured.
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
            else:
                text = getattr(item, "text", None)
            if text:
                text_parts.append(text)
        return "\n".join(text_parts).strip()

    return str(content).strip()


def _extract_json_payload(raw_text: str) -> dict[str, Any]:
    """
    Parse JSON payload from model text.

    Handles direct JSON, fenced JSON blocks, and text that includes a JSON object.
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned empty content.")

    cleaned = raw_text.strip()

    # If wrapped in ```json ... ``` fences, unwrap first.
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
            cleaned = "\n".join(lines[1:-1]).strip()

    # First attempt: entire payload is JSON.
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        # Second attempt: find first decodable JSON object/array in text.
        decoder = json.JSONDecoder()
        parsed = None
        for idx, char in enumerate(cleaned):
            if char not in "{[":
                continue
            try:
                parsed, _ = decoder.raw_decode(cleaned[idx:])
                break
            except json.JSONDecodeError:
                continue

        if parsed is None:
            preview = cleaned[:240].replace("\n", "\\n")
            raise ValueError(f"Unable to parse JSON from model output. Preview: {preview!r}") from None

    if not isinstance(parsed, dict):
        raise ValueError("Model response must be a JSON object at root.")

    return parsed


def _request_slide_plan(prompt: str) -> dict[str, Any]:
    """
    Request a slide plan from OpenAI and parse it as JSON.
    """
    client = _get_client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    return _extract_json_payload(_safe_message_text(response))


def _is_flow_slide_candidate(slide: dict[str, Any]) -> bool:
    """
    Return True when a slide likely benefits from a flow diagram.
    """
    if str(slide.get("type", "")).strip().lower() == "diagram":
        return True

    text_chunks = [
        str(slide.get("title", "")),
        str(slide.get("subtitle", "")),
        str(slide.get("speaker_notes", "")),
        " ".join(str(b) for b in (slide.get("bullets") or [])),
    ]
    pool = " ".join(text_chunks).lower()

    flow_keywords = (
        "workflow",
        "process",
        "pipeline",
        "architecture",
        "sequence",
        "lifecycle",
        "system",
        "flow",
        "steps",
    )
    return any(keyword in pool for keyword in flow_keywords)


def _wrap_mermaid_label(text: str, line_len: int = 24) -> str:
    """
    Wrap label text with <br/> so Mermaid nodes stay readable.
    """
    words = text.split()
    if not words:
        return text

    lines = []
    current = words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= line_len:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "<br/>".join(lines)


def _short_label(text: str, fallback: str, max_len: int = 120) -> str:
    """
    Build concise Mermaid node labels.
    """
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    cleaned = re.sub(r"^[\-\d\.\)\(:\s]+", "", cleaned).strip()
    if not cleaned:
        cleaned = fallback
    if len(cleaned) > max_len:
        # Cut at a word boundary to avoid clipping important words mid-token.
        truncated = cleaned[:max_len].rstrip()
        if " " in truncated:
            truncated = truncated.rsplit(" ", 1)[0]
        cleaned = truncated
    return _wrap_mermaid_label(cleaned)


def _is_comparison_slide(topic: str, slide: dict[str, Any]) -> bool:
    """
    Return True when the slide is primarily a comparison, not a process flow.
    """
    bullets = slide.get("bullets") or []
    text_chunks = [
        topic,
        str(slide.get("title", "")),
        str(slide.get("subtitle", "")),
        str(slide.get("speaker_notes", "")),
        " ".join(str(b) for b in bullets),
    ]
    pool = " ".join(text_chunks).lower()

    comparison_keywords = (
        " vs ",
        " versus ",
        "compare",
        "comparison",
        "compared",
        "alternatives",
        "pros and cons",
        "pros & cons",
        "which should you choose",
    )
    return any(keyword in pool for keyword in comparison_keywords)


def _extract_comparison_providers(topic: str, slide: dict[str, Any]) -> list[str]:
    """
    Extract provider/platform names from the topic and slide text.
    """
    bullets = slide.get("bullets") or []
    pool = " ".join(
        [
            topic,
            str(slide.get("title", "")),
            str(slide.get("subtitle", "")),
            " ".join(str(b) for b in bullets),
        ]
    )
    pool_lower = pool.lower()

    provider_patterns = [
        ("Amazon Web Services", ("amazon web services",)),
        ("AWS", ("aws",)),
        ("Microsoft Azure", ("microsoft azure",)),
        ("Azure", ("azure",)),
        ("Google Cloud Platform", ("google cloud platform",)),
        ("Google Cloud", ("google cloud",)),
        ("GCP", ("gcp",)),
    ]

    providers = []
    seen = set()
    for label, patterns in provider_patterns:
        if any(pattern in pool_lower for pattern in patterns) and label not in seen:
            seen.add(label)
            providers.append(label)

    # Collapse long/short duplicates while preserving familiar short labels on slides.
    normalized = []
    for provider in providers:
        short = (
            "AWS" if "aws" in provider.lower() else
            "Azure" if "azure" in provider.lower() else
            "GCP" if "google cloud" in provider.lower() or provider == "GCP" else
            provider
        )
        if short not in normalized:
            normalized.append(short)
    return normalized


def _extract_bullet_category_details(bullets: list[Any]) -> list[tuple[str, list[tuple[str, str]]]]:
    """
    Parse bullets like 'Compute: EC2 (AWS) vs VM (Azure)' into comparison details.
    """
    details = []
    provider_aliases = {
        "aws": "AWS",
        "azure": "Azure",
        "gcp": "GCP",
        "google cloud platform": "GCP",
        "google cloud": "GCP",
        "amazon web services": "AWS",
        "microsoft azure": "Azure",
    }

    for raw_bullet in bullets or []:
        bullet = sanitize_text(raw_bullet)
        if ":" not in bullet:
            continue

        category, rest = bullet.split(":", 1)
        category_label = _short_label(category, "Category", max_len=40)
        matches = re.findall(r'([^,;]+?)\s*\((AWS|Azure|GCP|Google Cloud Platform|Google Cloud|Amazon Web Services|Microsoft Azure)\)', rest, flags=re.IGNORECASE)
        entries = []
        for value, provider in matches:
            provider_key = provider_aliases.get(provider.strip().lower())
            value_label = _short_label(value, "Service", max_len=42)
            if provider_key and value_label:
                entries.append((provider_key, value_label))

        if entries:
            details.append((category_label, entries))

    return details


def _build_comparison_fallback_mermaid(topic: str, slide: dict[str, Any]) -> str:
    """
    Create a comparison-specific Mermaid diagram for versus/comparison topics.
    """
    title = str(slide.get("title", ""))
    bullets = slide.get("bullets") or []
    context = f"{topic} {title}".lower()
    root_label = _short_label(title or topic, "Comparison Overview", max_len=48)
    providers = _extract_comparison_providers(topic, slide)
    category_details = _extract_bullet_category_details(bullets)

    lines = ["flowchart TD", f'  ROOT["{root_label.replace("\"", "\\\"")}"]']

    if category_details:
        for idx, (category, entries) in enumerate(category_details[:4], start=1):
            category_id = f"C{idx}"
            lines.append(f'  ROOT --> {category_id}["{category.replace("\"", "\\\"")}"]')
            for sub_idx, (provider, value) in enumerate(entries[:3], start=1):
                node_id = f"{category_id}P{sub_idx}"
                label = f"{provider}: {value}"
                lines.append(f'  {category_id} --> {node_id}["{label.replace("\"", "\\\"")}"]')
        return "\n".join(lines)

    if not providers:
        providers = ["Option A", "Option B"]

    if "architecture" in context:
        categories = ["Compute Layer", "Storage Layer", "Network Layer", "Identity Layer"]
    elif any(keyword in context for keyword in ("service", "feature", "capability")):
        categories = ["Compute Services", "Storage Services", "Database Services"]
    elif "pricing" in context:
        categories = ["Pricing Model", "Discount Options", "Cost Controls"]
    else:
        categories = ["Core Strengths", "Ecosystem Fit", "Operations Model"]

    for idx, category in enumerate(categories[:4], start=1):
        category_id = f"C{idx}"
        lines.append(f'  ROOT --> {category_id}["{category}"]')
        for provider_idx, provider in enumerate(providers[:3], start=1):
            node_id = f"{category_id}P{provider_idx}"
            label = f"{provider} {category}"
            lines.append(f'  {category_id} --> {node_id}["{label}"]')

    return "\n".join(lines)


def _build_fallback_mermaid(topic: str, slide: dict[str, Any]) -> str | None:
    """
    Create a deterministic flowchart when the model omits one.
    """
    title = str(slide.get("title", ""))
    bullets = slide.get("bullets") or []
    context = f"{topic} {title}".lower()
    bullet_steps = [_short_label(str(b), "Step") for b in bullets if str(b).strip()]

    # Comparison slides need a comparison-specific diagram, not a fake process flow.
    if _is_comparison_slide(topic, slide):
        return _build_comparison_fallback_mermaid(topic, slide)

    # 1) Prefer slide-specific bullet content when available.
    if len(bullet_steps) >= 3:
        steps = bullet_steps[:5]
    # 2) Use architecture-specific flow for architecture slides.
    elif "architecture" in context:
        steps = [
            "User Query",
            "Retriever",
            "Vector Database",
            "Context Builder",
            "LLM Generator",
            "Final Answer",
        ]
    # 3) Use workflow/process flow for workflow-style slides.
    elif any(k in context for k in ("workflow", "process", "pipeline", "lifecycle", "sequence")):
        steps = [
            "User Query",
            "Retrieve Relevant Documents",
            "Augment Prompt with Retrieved Context",
            "Generate Grounded Response",
            "Return Final Answer",
        ]
    # 4) Generic fallback for all other cases.
    else:
        topic_label = _short_label(topic, "Topic")
        title_label = _short_label(title, f"{topic_label} Input")
        steps = [
            title_label,
            "Retrieve Context",
            "Process Information",
            "Generate Output",
            "Deliver Result",
        ]

    lines = ["flowchart TD"]
    for idx, label in enumerate(steps, start=1):
        escaped_label = label.replace('"', '\\"')
        # Use quoted labels for multiline/HTML-safe Mermaid text.
        lines.append(f'  S{idx}["{escaped_label}"]')
    for idx in range(1, len(steps)):
        lines.append(f"  S{idx} --> S{idx+1}")
    return "\n".join(lines)


def _ensure_flow_diagrams(plan: dict[str, Any], topic: str) -> dict[str, Any]:
    """
    Ensure flow/process slides always have a valid Mermaid diagram.
    """
    slides = plan.get("slides") or []
    seen_fallback_diagrams = set()
    for idx, slide in enumerate(slides, start=1):
        if str(slide.get("type", "")).strip().lower() == "title":
            continue

        current_diagram = str(slide.get("diagram", "") or "")
        if _is_flow_slide_candidate(slide) and not is_valid_mermaid(current_diagram):
            fallback_diagram = _build_fallback_mermaid(topic, slide)
            if not fallback_diagram:
                print(f"  [plan] Slide {idx}: skipped fallback flowchart for comparison-style slide")
                continue
            if fallback_diagram in seen_fallback_diagrams:
                # Avoid repeating identical fallback flowcharts across slides.
                continue
            slide["diagram"] = fallback_diagram
            seen_fallback_diagrams.add(fallback_diagram)
            print(f"  [plan] Slide {idx}: inserted fallback flowchart")
    return plan


def _normalize_slide_backup_fields(plan: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure optional backup fields always exist in the slide plan.
    """
    for slide in plan.get("slides", []) or []:
        if not isinstance(slide.get("bullets"), list):
            slide["bullets"] = []
        if not isinstance(slide.get("diagram_bullets"), list):
            slide["diagram_bullets"] = []
    return plan


def generate_slide_plan(topic, num_slides=16):
    """
    Generate a complete slide plan for a presentation topic using GPT-5.4-mini.

    Args:
        topic (str): The presentation topic
        num_slides (int): The number of slides to generate (default 16)

    Returns:
        dict: Slide plan with structure: {title, slides: [{type, title, subtitle, icon,
              image_query, bullets, diagram, code, chart, speaker_notes}, ...]}

    Description:
        Loads the prompt template from the bundled marp_core/templates/prompt.md file.
        Sends it to GPT-5.4-mini with the topic and num_slides substituted.
        Parses JSON response and ensures first slide is a title slide.
        Returns structured slide plan ready for rendering.
    """
    # Load bundled prompt template using importlib.resources (works when installed as a package)
    try:
        prompt_template = resources.files("marp_core.templates").joinpath("prompt.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        print("ERROR: bundled prompt.md not found inside the marp_core package.")
        exit(1)

    # Substitute {topic} and {num_slides} placeholders in the prompt using replace (safer than format())
    # format() would fail because JSON schema contains {} braces
    prompt = prompt_template.replace("{topic}", topic).replace("{num_slides}", str(num_slides))

    # Generate and parse JSON slide plan.
    # Retry once with a stricter instruction if parsing fails.
    try:
        plan = _request_slide_plan(prompt)
    except ValueError as first_error:
        retry_prompt = (
            f"{prompt}\n\n"
            "CRITICAL: Return only one valid JSON object that matches the schema. "
            "Do not include markdown fences or any prose."
        )
        try:
            plan = _request_slide_plan(retry_prompt)
        except ValueError as second_error:
            raise ValueError(
                "Failed to parse slide plan JSON from model output after retry.\n"
                f"First attempt: {first_error}\n"
                f"Second attempt: {second_error}"
            ) from second_error

    if not isinstance(plan.get("slides"), list):
        plan["slides"] = []

    # Ensure first slide is a title slide (safety check in case GPT fails)
    if not plan.get("slides") or plan["slides"][0].get("type") != "title":
        # Insert default title slide at the beginning
        plan.setdefault("slides", []).insert(0, {
            "type": "title",
            "title": topic,
            "subtitle": f"A concise overview of {topic}",
            "icon": "",
            "image_query": topic,
            "bullets": [],
            "diagram": "",
            "diagram_bullets": [],
            "code": {"language": "", "content": ""},
            "chart": {"type": "", "description": "", "labels": [], "values": []},
            "speaker_notes": "Title slide introducing the topic and setting visual tone."
        })

    plan = _normalize_slide_backup_fields(plan)

    # Guarantee that workflow/process slides carry renderable Mermaid diagrams.
    plan = _ensure_flow_diagrams(plan, topic)

    # Optimize diagram placement: defer diagrams from overcrowded slides to next slide
    print("Optimizing diagram placement...")
    plan = optimize_diagram_placement(plan)

    return plan
