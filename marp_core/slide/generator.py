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
    slide_type = str(slide.get("type", "")).strip().lower()
    if slide_type == "diagram":
        return True

    if slide_type in {"title", "chart", "code"}:
        return False

    bullets = [sanitize_text(bullet) for bullet in (slide.get("bullets") or []) if sanitize_text(bullet)]
    if len(bullets) < 2:
        return False

    text_chunks = [
        str(slide.get("title", "")),
        str(slide.get("subtitle", "")),
        str(slide.get("speaker_notes", "")),
        " ".join(bullets),
    ]
    pool = " ".join(text_chunks).lower()

    positive_keywords = (
        "workflow",
        "process",
        "pipeline",
        "architecture",
        "sequence",
        "lifecycle",
        "system",
        "flow",
        "steps",
        "tooling",
        "ecosystem",
        "stack",
        "integration",
        "deployment",
        "components",
        "model",
    )
    negative_keywords = (
        "introduction",
        "overview",
        "summary",
        "benefits",
        "strengths",
        "features",
        "conclusion",
        "thank you",
    )

    positive_match = any(keyword in pool for keyword in positive_keywords)
    negative_match = any(keyword in pool for keyword in negative_keywords)
    comparison_like = len(_extract_comparison_providers("", slide)) >= 2

    node_labels = []
    seen_labels = set()
    for bullet in bullets[:5]:
        label = _derive_bullet_node_label(str(slide.get("title", "")), bullet)
        if not label:
            continue
        normalized = re.sub(r"\s+", " ", label).strip().lower()
        if normalized in seen_labels or _is_generic_node_label(normalized):
            continue
        seen_labels.add(normalized)
        node_labels.append(label)

    has_concrete_structure = len(node_labels) >= 2
    if comparison_like:
        return has_concrete_structure

    return has_concrete_structure and positive_match and not negative_match


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


def _extract_generic_comparison_entities(text: str) -> list[str]:
    """
    Extract generic comparison entities from text like 'Python vs Rust'.
    """
    cleaned = sanitize_text(text)
    if not cleaned:
        return []

    normalized = re.sub(r"\b(vs\.?|versus|compared to)\b", "|", cleaned, flags=re.IGNORECASE)
    if "|" not in normalized:
        return []

    entities = []
    seen = set()
    for raw_part in normalized.split("|"):
        part = raw_part.strip(" ,.;:()[]{}")
        if not part:
            continue

        # Keep the most specific tail segment from titles like
        # 'Overview of Python' or 'Top languages: Python'.
        if ":" in part:
            part = part.split(":")[-1].strip()
        if " - " in part:
            part = part.split(" - ")[-1].strip()

        part = re.sub(
            r"^(overview of|introduction to|guide to|about|the|a|an)\s+",
            "",
            part,
            flags=re.IGNORECASE,
        )
        part = re.sub(
            r"\s+(comparison|overview|workflow|flow|architecture|benefits|strengths|features)$",
            "",
            part,
            flags=re.IGNORECASE,
        ).strip(" ,.;:()[]{}")

        words = part.split()
        if not words:
            continue
        if len(words) > 4:
            part = " ".join(words[-4:])

        key = part.lower()
        if key not in seen:
            seen.add(key)
            entities.append(part)

    return entities[:4]


def _is_comparison_slide(topic: str, slide: dict[str, Any]) -> bool:
    """
    Return True when the slide is primarily a comparison, not a process flow.
    """
    bullets = slide.get("bullets") or []
    slide_text_chunks = [
        str(slide.get("title", "")),
        str(slide.get("subtitle", "")),
        str(slide.get("speaker_notes", "")),
        " ".join(str(b) for b in bullets),
    ]
    pool = " ".join(slide_text_chunks).lower()

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
    if any(keyword in pool for keyword in comparison_keywords):
        return True

    slide_entities = _extract_generic_comparison_entities(" ".join(slide_text_chunks))
    if len(slide_entities) >= 2:
        return True

    slide_providers = _extract_comparison_providers("", slide)
    return len(slide_providers) >= 2


def _extract_comparison_providers(topic: str, slide: dict[str, Any]) -> list[str]:
    """
    Extract provider/platform names from the topic and slide text.
    """
    bullets = slide.get("bullets") or []
    providers = []
    seen = set()

    def _append_provider(label: str) -> None:
        candidate = sanitize_text(label)
        if not candidate:
            return
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            providers.append(candidate)

    for entity in _extract_generic_comparison_entities(topic):
        _append_provider(entity)
    for entity in _extract_generic_comparison_entities(str(slide.get("title", ""))):
        _append_provider(entity)
    for entity in _extract_generic_comparison_entities(str(slide.get("subtitle", ""))):
        _append_provider(entity)

    generic_entities = {
        "both", "all", "each", "comparison", "alternatives", "pros", "cons",
        "overview", "introduction", "workflow", "flow", "architecture",
    }

    for raw_bullet in bullets:
        bullet = sanitize_text(raw_bullet)
        if not bullet:
            continue

        for entity in _extract_generic_comparison_entities(bullet):
            _append_provider(entity)

        colon_match = re.match(r"^\s*([^:]{1,40})\s*:", bullet)
        if colon_match:
            left_side = sanitize_text(colon_match.group(1))
            if left_side and left_side.lower() not in generic_entities and len(left_side.split()) <= 3:
                _append_provider(left_side)

        possessive_matches = re.findall(r"\b([A-Z][A-Za-z0-9+#\.-]*(?:\s+[A-Z][A-Za-z0-9+#\.-]*){0,2})(?:'s)\b", bullet)
        for entity in possessive_matches:
            if entity.lower() not in generic_entities:
                _append_provider(entity)

        subject_match = re.match(
            r"^\s*([A-Z][A-Za-z0-9+#\.-]*(?:\s+[A-Z][A-Za-z0-9+#\.-]*){0,2})\s+"
            r"(?:has|have|is|are|offers|offer|uses|use|includes|include|provides|provide)\b",
            bullet,
        )
        if subject_match:
            entity = sanitize_text(subject_match.group(1))
            if entity and entity.lower() not in generic_entities:
                _append_provider(entity)

        paren_matches = re.findall(r"\(([^)]+)\)", bullet)
        for entity in paren_matches:
            candidate = sanitize_text(entity)
            if candidate and candidate.lower() not in generic_entities and len(candidate.split()) <= 4:
                _append_provider(candidate)

    return providers[:4]


def _extract_bullet_category_details(
    bullets: list[Any],
    providers: list[str],
) -> list[tuple[str, list[tuple[str, str]]]]:
    """
    Parse bullets like 'Compute: EC2 (AWS) vs VM (Azure)' into comparison details.
    """
    details = []
    provider_lookup = {provider.lower(): provider for provider in providers}

    for raw_bullet in bullets or []:
        bullet = sanitize_text(raw_bullet)
        if ":" not in bullet:
            continue

        category, rest = bullet.split(":", 1)
        category_label = _short_label(category, "Category", max_len=40)
        matches = re.findall(r'([^,;]+?)\s*\(([^)]+)\)', rest)
        entries = []
        for value, provider in matches:
            provider_text = sanitize_text(provider)
            provider_key = provider_lookup.get(provider_text.lower(), provider_text)
            value_label = _short_label(value, "Service", max_len=42)
            if provider_key and value_label:
                entries.append((provider_key, value_label))

        if entries:
            details.append((category_label, entries))

    return details


def _extract_content_words(text: str) -> list[str]:
    """
    Return lowercase content words with generic filler removed.
    """
    stopwords = {
        "a", "an", "the", "and", "or", "but", "for", "of", "to", "in", "on", "at",
        "by", "with", "from", "into", "over", "under", "through", "during", "after",
        "before", "between", "without", "within", "about", "across", "around", "per",
        "is", "are", "was", "were", "be", "been", "being", "has", "have", "had",
        "do", "does", "did", "can", "could", "should", "would", "may", "might",
        "will", "shall", "this", "that", "these", "those", "it", "its", "their",
        "his", "her", "our", "your", "both", "all", "each", "more", "most", "less",
        "very", "large", "small", "strong", "active", "rapidly", "increasing",
        "known", "often", "generally", "extensive", "available", "ideal", "best",
        "better", "worse", "gentle", "steeper", "deep", "deeper", "high", "low",
        "varies", "vary", "language", "languages", "growing", "one", "two", "three",
    }
    words = re.findall(r"[A-Za-z0-9+#\.-]+", sanitize_text(text).lower())
    return [word for word in words if len(word) > 1 and word not in stopwords]


def _is_generic_node_label(label: str) -> bool:
    """
    Return True when a derived node label is too vague to be useful in a diagram.
    """
    generic_words = {
        "overview", "summary", "details", "features", "benefits", "strengths",
        "workflow", "process", "flow", "pipeline", "system", "systems",
        "architecture", "model", "models", "ecosystem", "tooling", "tools",
        "comparison", "analysis", "information", "context", "output", "result",
        "input", "step", "steps", "component", "components",
    }
    words = set(_extract_content_words(label))
    return bool(words) and words.issubset(generic_words)


def _extract_conjunction_phrase(text: str) -> str:
    """
    Prefer phrases like 'libraries and frameworks' or 'docs and support'.
    """
    cleaned = sanitize_text(text)
    if not cleaned:
        return ""

    match = re.search(
        r"\b([A-Za-z0-9+#\.-]+(?:\s+[A-Za-z0-9+#\.-]+){0,2}\s+(?:and|or|&)\s+[A-Za-z0-9+#\.-]+(?:\s+[A-Za-z0-9+#\.-]+){0,2})\b",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""

    phrase = sanitize_text(match.group(1))
    phrase_tokens = phrase.split()
    if len(phrase_tokens) >= 3:
        for idx, token in enumerate(phrase_tokens):
            lowered = token.lower()
            if lowered in {"and", "or", "&"} and idx > 0 and idx < len(phrase_tokens) - 1:
                phrase = " ".join(phrase_tokens[max(0, idx - 2):min(len(phrase_tokens), idx + 3)])
                break

    phrase_words = _extract_content_words(phrase)
    if len(phrase_words) < 2:
        return ""
    return _short_label(phrase, "Comparison Area", max_len=40).replace("<br/>", " ")


def _format_category_label(label: str) -> str:
    """
    Normalize dynamic category labels for slide-friendly display.
    """
    words = sanitize_text(label).split()
    if not words:
        return "Comparison Area"
    return " ".join(word if word.isupper() else word.capitalize() for word in words)


def _derive_dynamic_category_label(
    title: str,
    bullet: str,
    providers: list[str],
    mentioned_providers: list[str],
) -> str:
    """
    Infer a category label from the slide title and bullet text without topic-specific rules.
    """
    if ":" in bullet:
        category, _ = bullet.split(":", 1)
        category_label = sanitize_text(category)
        if category_label:
            formatted = _short_label(category_label, "Comparison Area", max_len=40).replace("<br/>", " ")
            return _format_category_label(formatted)

    conjunction_phrase = _extract_conjunction_phrase(bullet)
    if conjunction_phrase:
        return _format_category_label(conjunction_phrase)

    title_words = set(_extract_content_words(title))
    bullet_text = sanitize_text(bullet)
    bullet_words = re.findall(r"[A-Za-z0-9+#\.-]+", bullet_text)
    overlap_words = []
    seen_overlap = set()
    for word in bullet_words:
        lowered = word.lower()
        if lowered in title_words and lowered not in seen_overlap:
            seen_overlap.add(lowered)
            overlap_words.append(word)
    if overlap_words:
        formatted = _short_label(" ".join(overlap_words), sanitize_text(title) or "Comparison Area", max_len=36).replace("<br/>", " ")
        return _format_category_label(formatted)

    claim_text = _clean_comparison_claim_text(bullet, providers, mentioned_providers)
    claim_words = re.findall(r"[A-Za-z0-9+#\.-]+", claim_text)
    content_words = _extract_content_words(claim_text)
    if content_words:
        selected = []
        for word in claim_words:
            lowered = word.lower()
            if lowered in content_words and lowered not in {w.lower() for w in selected}:
                selected.append(word)
            if len(selected) == 3:
                break
        if selected:
            formatted = _short_label(" ".join(selected), sanitize_text(title) or "Comparison Area", max_len=36).replace("<br/>", " ")
            return _format_category_label(formatted)

    title_label = sanitize_text(title)
    if title_label:
        formatted = _short_label(title_label, "Comparison Area", max_len=36).replace("<br/>", " ")
        return _format_category_label(formatted)

    return "Comparison Area"


def _clean_comparison_claim_text(bullet: str, providers: list[str], mentioned_providers: list[str]) -> str:
    """
    Remove provider names and boilerplate so comparison node labels stay concise.
    """
    cleaned = sanitize_text(bullet)
    if not cleaned:
        return ""

    provider_names = providers if providers else mentioned_providers
    for provider in provider_names:
        pattern = re.escape(provider)
        cleaned = re.sub(rf"\b{pattern}(?:'s)?\b", "", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.strip()

    cleaned = re.sub(
        r"^\s*(both languages|both platforms|both providers|both|all languages|each language)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^\s*(have|has|is|are|offers|offer|supports|support|uses|use|employs|employ|provides|provide|includes|include)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"^\s*(a|an|the)\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,:;-")
    return cleaned


def _derive_bullet_node_label(title: str, bullet: str) -> str:
    """
    Build a compact concept label from a bullet without copying the full sentence.
    """
    cleaned_bullet = sanitize_text(bullet)
    if not cleaned_bullet:
        return ""

    context_prefix = ""
    if ":" in cleaned_bullet:
        left_side, right_side = cleaned_bullet.split(":", 1)
        left_label = sanitize_text(left_side)
        left_words = _extract_content_words(left_label)
        if left_label and len(left_words) >= 2 and not _is_generic_node_label(left_label):
            return _format_category_label(
                _short_label(left_label, sanitize_text(title) or "Detail", max_len=34).replace("<br/>", " ")
            )
        context_prefix = left_label
        cleaned_bullet = sanitize_text(right_side)

    conjunction_phrase = _extract_conjunction_phrase(cleaned_bullet)
    if conjunction_phrase:
        if context_prefix and context_prefix.lower() not in conjunction_phrase.lower():
            return _format_category_label(
                _short_label(f"{context_prefix} {conjunction_phrase}", conjunction_phrase, max_len=34).replace("<br/>", " ")
            )
        return _format_category_label(conjunction_phrase)

    generic_title_words = {
        "workflow", "process", "flow", "pipeline", "system", "systems",
        "architecture", "model", "models", "ecosystem", "tooling", "tools",
        "comparison", "overview", "summary", "stack", "components",
    }
    title_words = {
        word for word in _extract_content_words(title)
        if word not in generic_title_words
    }
    bullet_words = re.findall(r"[A-Za-z0-9+#\.-]+", cleaned_bullet)
    selected = []
    seen = set()
    for word in bullet_words:
        lowered = word.lower()
        if lowered in title_words and lowered not in seen:
            seen.add(lowered)
            selected.append(word)
    if selected:
        label = _short_label(" ".join(selected), sanitize_text(title) or "Detail", max_len=34).replace("<br/>", " ")
        if context_prefix and context_prefix.lower() not in label.lower():
            label = _short_label(f"{context_prefix} {label}", label, max_len=34).replace("<br/>", " ")
        return _format_category_label(label)

    content_words = _extract_content_words(cleaned_bullet)
    selected = []
    seen = set()
    for word in bullet_words:
        lowered = word.lower()
        if lowered in content_words and lowered not in seen:
            seen.add(lowered)
            selected.append(word)
        if len(selected) == 4:
            break

    if selected:
        label = _short_label(" ".join(selected), sanitize_text(title) or "Detail", max_len=34).replace("<br/>", " ")
        if context_prefix and context_prefix.lower() not in label.lower():
            label = _short_label(f"{context_prefix} {label}", label, max_len=34).replace("<br/>", " ")
        return _format_category_label(label)

    label = _short_label(cleaned_bullet, sanitize_text(title) or "Detail", max_len=34).replace("<br/>", " ")
    if context_prefix and context_prefix.lower() not in label.lower():
        label = _short_label(f"{context_prefix} {label}", label, max_len=34).replace("<br/>", " ")
    return _format_category_label(label)


def _infer_comparison_category_details(
    title: str,
    bullets: list[Any],
    providers: list[str],
) -> list[tuple[str, list[tuple[str, str]]]]:
    """
    Derive comparison categories and provider-specific claims from free-form bullets.
    """
    if not bullets or not providers:
        return []

    category_map: dict[str, dict[str, str]] = {}

    for raw_bullet in bullets:
        bullet = sanitize_text(raw_bullet)
        if not bullet:
            continue

        bullet_lower = bullet.lower()
        mentioned_providers = [
            provider for provider in providers
            if re.search(rf"\b{re.escape(provider)}(?:'s)?\b", bullet, flags=re.IGNORECASE)
        ]

        applies_to_all = any(
            marker in bullet_lower
            for marker in ("both languages", "both platforms", "both providers", "both", "all languages", "each language")
        )

        category = _derive_dynamic_category_label(title, bullet, providers, mentioned_providers)
        claim_text = _clean_comparison_claim_text(bullet, providers, mentioned_providers)
        if not claim_text:
            claim_text = bullet

        target_providers = providers[:3] if applies_to_all or not mentioned_providers else mentioned_providers[:3]
        category_entries = category_map.setdefault(category, {})

        for provider in target_providers:
            value = _short_label(claim_text, category, max_len=44).replace("<br/>", " ")
            existing = category_entries.get(provider)
            if existing and value.lower() not in existing.lower():
                category_entries[provider] = _short_label(f"{existing}; {value}", existing, max_len=52).replace("<br/>", " ")
            elif not existing:
                category_entries[provider] = value

    inferred_details = []
    for category, provider_claims in category_map.items():
        entries = [(provider, claim) for provider, claim in provider_claims.items() if claim]
        if entries:
            inferred_details.append((category, entries))

    return inferred_details[:4]


def _build_comparison_fallback_mermaid(topic: str, slide: dict[str, Any]) -> str:
    """
    Create a comparison-specific Mermaid diagram for versus/comparison topics.
    """
    title = str(slide.get("title", ""))
    bullets = slide.get("bullets") or []
    root_label = _short_label(title or topic, "Comparison Overview", max_len=48)
    providers = _extract_comparison_providers(topic, slide)
    category_details = _extract_bullet_category_details(bullets, providers)
    inferred_category_details = _infer_comparison_category_details(title, bullets, providers)

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

    if inferred_category_details:
        for idx, (category, entries) in enumerate(inferred_category_details[:4], start=1):
            category_id = f"C{idx}"
            lines.append(f'  ROOT --> {category_id}["{category.replace("\"", "\\\"")}"]')
            for sub_idx, (provider, value) in enumerate(entries[:3], start=1):
                node_id = f"{category_id}P{sub_idx}"
                label = f"{provider}: {value}"
                lines.append(f'  {category_id} --> {node_id}["{label.replace("\"", "\\\"")}"]')
        return "\n".join(lines)

    # If we cannot derive provider-specific comparison areas from the actual
    # slide content, skip the diagram entirely rather than inventing a shallow
    # "topic -> provider names" tree that adds little presentation value.
    return None


def _is_sequential_flow_slide(slide: dict[str, Any]) -> bool:
    """
    Return True when the slide should render as a step-by-step sequence.
    """
    text_chunks = [
        str(slide.get("title", "")),
        str(slide.get("subtitle", "")),
        str(slide.get("speaker_notes", "")),
        " ".join(str(bullet) for bullet in (slide.get("bullets") or [])),
    ]
    pool = " ".join(text_chunks).lower()
    sequential_keywords = (
        "workflow",
        "process",
        "pipeline",
        "sequence",
        "lifecycle",
        "step",
        "steps",
        "journey",
        "roadmap",
    )
    return any(keyword in pool for keyword in sequential_keywords)


def _build_fallback_diagram_payload(topic: str, slide: dict[str, Any]) -> tuple[str | None, str]:
    """
    Build a fallback diagram plus metadata describing how derived it is.
    """
    title = str(slide.get("title", ""))
    bullets = slide.get("bullets") or []

    if _is_comparison_slide(topic, slide):
        diagram = _build_comparison_fallback_mermaid(topic, slide)
        return diagram, "fallback_derived" if diagram else ""

    if len(bullets) < 2:
        return None, ""

    root_label = _short_label(title or topic, _short_label(topic, "Topic"), max_len=48)
    lines = ["flowchart TD", f'  ROOT["{root_label.replace("\"", "\\\"")}"]']

    node_labels = []
    seen_labels = set()
    for raw_bullet in bullets[:5]:
        label = _derive_bullet_node_label(title, str(raw_bullet))
        if not label:
            continue
        normalized = label.lower()
        if normalized in seen_labels or _is_generic_node_label(normalized):
            continue
        seen_labels.add(normalized)
        node_labels.append(label)

    if len(node_labels) < 2:
        return None, ""

    if _is_sequential_flow_slide(slide):
        first_label = node_labels[0].replace('"', '\\"')
        lines.append(f'  ROOT --> B1["{first_label}"]')
        for idx in range(1, len(node_labels)):
            escaped_label = node_labels[idx].replace('"', '\\"')
            lines.append(f'  B{idx} --> B{idx+1}["{escaped_label}"]')
    else:
        for idx, label in enumerate(node_labels, start=1):
            escaped_label = label.replace('"', '\\"')
            lines.append(f'  ROOT --> B{idx}["{escaped_label}"]')

    return "\n".join(lines), "fallback_derived"


def _build_fallback_mermaid(topic: str, slide: dict[str, Any]) -> str | None:
    """
    Create a deterministic flowchart when the model omits one.
    """
    diagram, _ = _build_fallback_diagram_payload(topic, slide)
    return diagram


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
            fallback_diagram, diagram_origin = _build_fallback_diagram_payload(topic, slide)
            if not fallback_diagram:
                print(f"  [plan] Slide {idx}: skipped fallback flowchart for comparison-style slide")
                continue
            if fallback_diagram in seen_fallback_diagrams:
                # Avoid repeating identical fallback flowcharts across slides.
                continue
            slide["diagram"] = fallback_diagram
            slide["diagram_origin"] = diagram_origin or "fallback"
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
        if "diagram_origin" not in slide:
            slide["diagram_origin"] = ""
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
