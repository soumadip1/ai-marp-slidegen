"""
Diagram optimization and deferral for slide overflow prevention.

Post-processes slide plans to move diagrams from content-heavy slides to the next slide.
"""

import re

from ..utils.validators import is_valid_mermaid
from ..utils.text import sanitize_text


MAX_DIAGRAM_SLIDES = 3
GENERIC_DIAGRAM_PHRASES = (
    "retrieve context",
    "process information",
    "generate output",
    "deliver result",
    "collect input",
    "process input",
    "final output",
    "final result",
    "start process",
    "end process",
    "step 1",
    "step 2",
    "step 3",
)
GENERIC_DIAGRAM_WORDS = {
    "retrieve", "context", "process", "information", "generate", "output", "deliver",
    "result", "input", "step", "steps", "phase", "phases", "workflow", "flow",
    "system", "systems", "module", "modules", "component", "components", "data",
    "analysis", "processing", "execution", "final", "start", "end", "task", "tasks",
    "operation", "operations", "overview",
}
CONTENT_STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "for", "of", "to", "in", "on", "at",
    "by", "with", "from", "into", "over", "under", "through", "during", "after",
    "before", "between", "without", "within", "about", "across", "around", "per",
    "is", "are", "was", "were", "be", "been", "being", "has", "have", "had",
    "do", "does", "did", "can", "could", "should", "would", "may", "might",
    "will", "shall", "this", "that", "these", "those", "it", "its", "their",
    "his", "her", "our", "your", "both", "all", "each", "more", "most", "less",
    "very", "often", "generally", "available", "best", "better", "worse",
}


def _slide_metrics(slide):
    """
    Compute text-density metrics for a slide.
    """
    bullets = slide.get("bullets") or []
    code = slide.get("code") or {}
    subtitle = slide.get("subtitle", "")

    num_bullets = len(bullets)
    has_code = bool(code.get("content"))
    has_subtitle = bool(str(subtitle).strip())
    bullet_char_count = sum(len(sanitize_text(b)) for b in bullets)
    has_long_bullets = any(len(sanitize_text(b)) >= 55 for b in bullets)

    # Content volume heuristic:
    # - Each bullet: 1 unit
    # - Code block: 2 units
    # - Subtitle: 1 unit
    content_volume = num_bullets + (2 if has_code else 0) + (1 if has_subtitle else 0)

    return {
        "num_bullets": num_bullets,
        "has_code": has_code,
        "has_subtitle": has_subtitle,
        "bullet_char_count": bullet_char_count,
        "has_long_bullets": has_long_bullets,
        "content_volume": content_volume,
    }


def _is_overcrowded_for_diagram(slide):
    """
    Return True when text/code density is too high for embedding a diagram.
    """
    m = _slide_metrics(slide)
    text_heavy = m["bullet_char_count"] >= 140 or m["has_long_bullets"]
    return (
        (m["num_bullets"] >= 3)
        or (m["num_bullets"] >= 2 and text_heavy)
        or (m["content_volume"] >= 5)
    )


def _make_diagram_only_slide(source_slide, diagram, diagram_bullets):
    """
    Create a dedicated diagram slide when no suitable target slide exists.
    """
    title = sanitize_text(source_slide.get("title")) or "Process Flow"
    return {
        "type": "diagram",
        "title": f"{title} Flow",
        "subtitle": "",
        "icon": sanitize_text(source_slide.get("icon")),
        "image_query": sanitize_text(source_slide.get("image_query")),
        "bullets": [],
        "diagram": diagram,
        "diagram_bullets": diagram_bullets or [],
        "code": {"language": "", "content": ""},
        "chart": {"type": "", "description": "", "labels": [], "values": []},
        "speaker_notes": f"Dedicated diagram view for: {title}",
    }


def _strip_diagram_suffix(title):
    """
    Remove common trailing diagram suffixes from a slide title.
    """
    cleaned = sanitize_text(title)
    stripped = re.sub(r"\s+(flow|workflow|process|diagram)\s*$", "", cleaned, flags=re.IGNORECASE)
    stripped = stripped.strip(" :-")
    return stripped or cleaned


def _extract_content_words(text):
    """
    Return lowercase content words with generic filler removed.
    """
    words = re.findall(r"[A-Za-z0-9+#\.-]+", sanitize_text(text).lower())
    return [word for word in words if len(word) > 1 and word not in CONTENT_STOPWORDS]


def _normalize_slide_subject(title):
    """
    Normalize a title so related content and follow-up flow slides can be matched.
    """
    cleaned = _strip_diagram_suffix(title).lower()
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def _slide_text_corpus(slide):
    """
    Build a normalized text corpus for duplicate-content checks.
    """
    chunks = [
        slide.get("title", ""),
        slide.get("subtitle", ""),
        slide.get("speaker_notes", ""),
    ]
    chunks.extend(slide.get("bullets") or [])
    chunks.extend(slide.get("diagram_bullets") or [])
    cleaned_chunks = [sanitize_text(chunk).lower() for chunk in chunks if sanitize_text(chunk)]
    return " ".join(cleaned_chunks)


def _extract_diagram_labels(diagram):
    """
    Extract readable node labels from Mermaid brackets for overlap checks.
    """
    labels = []
    for raw_label in re.findall(r"\[([^\]]+)\]", str(diagram or "")):
        cleaned = sanitize_text(
            raw_label.replace("<br/>", " ").replace("<br />", " ").replace("<br>", " ")
        ).lower()
        if cleaned:
            labels.append(cleaned)
    return labels


def _diagram_is_too_generic(slide, deck_title=""):
    """
    Return True when a Mermaid diagram uses vague placeholder labels.
    """
    labels = _extract_diagram_labels(slide.get("diagram", ""))
    if not labels:
        return False

    normalized_title = _normalize_slide_subject(slide.get("title", ""))
    candidate_labels = [
        label for label in labels
        if _normalize_slide_subject(label) != normalized_title
    ]
    if not candidate_labels:
        return False

    context_words = set(
        _extract_content_words(
            " ".join(
                [
                    deck_title,
                    slide.get("title", ""),
                    slide.get("subtitle", ""),
                    slide.get("speaker_notes", ""),
                    " ".join(slide.get("bullets") or []),
                    " ".join(slide.get("diagram_bullets") or []),
                ]
            )
        )
    )

    generic_phrase_hits = 0
    abstract_label_hits = 0
    context_hits = 0

    for label in candidate_labels:
        lower_label = label.lower()
        label_words = set(_extract_content_words(label))

        if any(phrase in lower_label for phrase in GENERIC_DIAGRAM_PHRASES):
            generic_phrase_hits += 1
            continue

        if label_words and label_words.issubset(GENERIC_DIAGRAM_WORDS):
            abstract_label_hits += 1

        if label_words & context_words:
            context_hits += 1

    abstract_total = generic_phrase_hits + abstract_label_hits
    if generic_phrase_hits >= 2:
        return True
    if generic_phrase_hits >= 1 and abstract_total >= max(2, len(candidate_labels) - 1):
        return True
    if len(candidate_labels) >= 3 and abstract_total >= len(candidate_labels) - 1 and context_hits == 0:
        return True

    return False


def _diagram_duplicates_prior_content(slide, prior_slides):
    """
    Return True when a diagram-only slide mostly repeats earlier slide content.
    """
    if slide.get("bullets"):
        return False

    current_subject = _normalize_slide_subject(slide.get("title", ""))
    diagram_labels = [label for label in _extract_diagram_labels(slide.get("diagram", "")) if len(label) >= 6]

    if not current_subject and not diagram_labels:
        return False

    for prior_slide in reversed(prior_slides):
        if str(prior_slide.get("type", "")).strip().lower() == "title":
            continue

        prior_subject = _normalize_slide_subject(prior_slide.get("title", ""))
        same_subject = bool(
            current_subject
            and prior_subject
            and (
                current_subject == prior_subject
                or current_subject in prior_subject
                or prior_subject in current_subject
            )
        )
        if not same_subject:
            continue

        prior_corpus = _slide_text_corpus(prior_slide)
        if not diagram_labels:
            return True

        overlap = sum(1 for label in diagram_labels if label in prior_corpus)
        if overlap >= max(2, (len(diagram_labels) + 1) // 2):
            return True

    return False


def _downgrade_or_drop_diagram_slide(slide):
    """
    Remove a diagram from a slide and keep bullet backup content when available.
    """
    fallback_bullets = [
        sanitize_text(bullet)
        for bullet in (slide.get("diagram_bullets") or slide.get("bullets") or [])
        if sanitize_text(bullet)
    ]

    slide["diagram"] = ""
    slide["diagram_bullets"] = []
    slide["diagram_origin"] = ""

    if str(slide.get("type", "")).strip().lower() != "diagram":
        return slide

    if not fallback_bullets:
        return None

    slide["type"] = "content"
    slide["title"] = _strip_diagram_suffix(slide.get("title", "")) or "Key Points"
    slide["bullets"] = fallback_bullets[:5]
    return slide


def _promote_to_diagram_only_slide(slide):
    """
    Turn a crowded slide into a diagram-focused slide instead of dropping the diagram.
    """
    backup_bullets = [
        sanitize_text(bullet)
        for bullet in (slide.get("diagram_bullets") or slide.get("bullets") or [])
        if sanitize_text(bullet)
    ]

    slide["type"] = "diagram"
    slide["subtitle"] = ""
    slide["bullets"] = []
    slide["code"] = {"language": "", "content": ""}
    slide["chart"] = {"type": "", "description": "", "labels": [], "values": []}
    slide["diagram_bullets"] = backup_bullets[:5]

    existing_notes = sanitize_text(slide.get("speaker_notes", ""))
    focus_note = "Diagram-focused slide showing the structure without duplicate bullet text."
    if focus_note.lower() not in existing_notes.lower():
        slide["speaker_notes"] = f"{existing_notes} {focus_note}".strip()

    return slide


def _enforce_diagram_policies(slides, deck_title="", max_diagram_slides=MAX_DIAGRAM_SLIDES):
    """
    Keep diagrams unique and cap the total number of diagram slides.
    """
    curated_slides = []
    kept_diagrams = 0

    for idx, slide in enumerate(slides, start=1):
        diagram = slide.get("diagram", "")
        has_valid_diagram = bool(diagram and is_valid_mermaid(diagram))

        if not has_valid_diagram:
            curated_slides.append(slide)
            continue

        if _diagram_is_too_generic(slide, deck_title=deck_title):
            downgraded = _downgrade_or_drop_diagram_slide(slide)
            if downgraded is None:
                print(f"  [optimizer] Removed overly generic diagram-only slide {idx}")
                continue
            curated_slides.append(downgraded)
            print(f"  [optimizer] Slide {idx}: removed overly generic diagram content")
            continue

        if _diagram_duplicates_prior_content(slide, curated_slides):
            downgraded = _downgrade_or_drop_diagram_slide(slide)
            if downgraded is None:
                print(f"  [optimizer] Removed duplicate diagram-only slide {idx}")
                continue
            curated_slides.append(downgraded)
            print(f"  [optimizer] Slide {idx}: removed duplicate diagram content")
            continue

        if kept_diagrams >= max_diagram_slides:
            downgraded = _downgrade_or_drop_diagram_slide(slide)
            if downgraded is None:
                print(f"  [optimizer] Removed diagram-only slide {idx} to keep within limit")
                continue
            curated_slides.append(downgraded)
            print(f"  [optimizer] Slide {idx}: removed diagram to keep within {max_diagram_slides}-slide limit")
            continue

        kept_diagrams += 1
        curated_slides.append(slide)

    return curated_slides


def optimize_diagram_placement(slide_plan):
    """
    Post-process slide plan to defer diagrams from overcrowded slides to later slides.

    If no suitable slide is available, inserts a dedicated diagram-only slide.
    """
    slides = slide_plan.get("slides", [])

    if not slides:
        return slide_plan

    # First pass: collect all diagrams that need to be deferred.
    deferred_diagrams = {}  # Maps slide index to deferred diagram payload

    for idx, slide in enumerate(slides):
        # Skip title slides - they handle diagrams differently.
        if slide.get("type") == "title":
            continue

        diagram = slide.get("diagram", "")
        has_valid_diagram = bool(diagram and is_valid_mermaid(diagram))

        if has_valid_diagram and _is_overcrowded_for_diagram(slide):
            m = _slide_metrics(slide)
            diagram_origin = str(slide.get("diagram_origin", "") or "").strip().lower()

            if m["num_bullets"] >= 2:
                slides[idx] = _promote_to_diagram_only_slide(slides[idx])
                print(
                    f"  [optimizer] Slide {idx+1}: Promoted crowded slide to diagram-only "
                    f"(bullets={m['num_bullets']}, chars={m['bullet_char_count']}, volume={m['content_volume']})"
                )
                continue

            # Verbatim fallback diagrams are generated from the slide's own
            # bullets/title without additional structure. When a slide is already
            # too crowded, moving that fallback diagram to a separate slide just
            # duplicates the previous slide's content instead of adding new
            # information. In that case, keep the bullets and drop the diagram.
            #
            # Derived fallback diagrams are allowed through because they condense
            # the slide into shorter structural labels rather than repeating the
            # original bullet sentences.
            if diagram_origin == "fallback_verbatim":
                slides[idx]["diagram"] = ""
                slides[idx]["diagram_bullets"] = []
                print(
                    f"  [optimizer] Slide {idx+1}: Dropped verbatim fallback diagram "
                    f"instead of deferring duplicate content "
                    f"(bullets={m['num_bullets']}, chars={m['bullet_char_count']}, volume={m['content_volume']})"
                )
                continue

            deferred_diagrams[idx] = {
                "diagram": diagram,
                "diagram_bullets": slide.get("diagram_bullets") or [],
            }
            slides[idx]["diagram"] = ""
            slides[idx]["diagram_bullets"] = []
            print(
                f"  [optimizer] Slide {idx+1}: Deferring diagram "
                f"(bullets={m['num_bullets']}, chars={m['bullet_char_count']}, volume={m['content_volume']})"
            )

    # Second pass: place deferred diagrams on the next suitable slides.
    # Process in reverse order to handle index shifts safely.
    for original_idx in sorted(deferred_diagrams.keys(), reverse=True):
        deferred_payload = deferred_diagrams[original_idx]
        deferred_diagram = deferred_payload["diagram"]
        deferred_diagram_bullets = deferred_payload["diagram_bullets"]

        target_idx = original_idx + 1
        placed = False

        while target_idx < len(slides):
            target_slide = slides[target_idx]

            if target_slide.get("type") != "title":
                existing_diagram = target_slide.get("diagram", "")
                target_is_available = not existing_diagram or not is_valid_mermaid(existing_diagram)
                target_has_space = not _is_overcrowded_for_diagram(target_slide)

                if target_is_available and target_has_space:
                    slides[target_idx]["diagram"] = deferred_diagram
                    slides[target_idx]["diagram_bullets"] = deferred_diagram_bullets
                    print(f"  [optimizer] Placed deferred diagram on slide {target_idx+1}")
                    placed = True
                    break

            target_idx += 1

        if not placed:
            source_slide = slides[original_idx] if original_idx < len(slides) else {}
            diagram_slide = _make_diagram_only_slide(source_slide, deferred_diagram, deferred_diagram_bullets)
            insert_at = min(original_idx + 1, len(slides))
            slides.insert(insert_at, diagram_slide)
            print(
                f"  [optimizer] Inserted dedicated diagram slide at {insert_at+1} "
                f"for deferred diagram from slide {original_idx+1}"
            )

    slide_plan["slides"] = _enforce_diagram_policies(
        slides,
        deck_title=slide_plan.get("title", ""),
    )
    return slide_plan
