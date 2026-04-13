"""
Diagram optimization and deferral for slide overflow prevention.

Post-processes slide plans to move diagrams from content-heavy slides to the next slide.
"""

from ..utils.validators import is_valid_mermaid
from ..utils.text import sanitize_text


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


def _make_diagram_only_slide(source_slide, diagram):
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
        "code": {"language": "", "content": ""},
        "chart": {"type": "", "description": "", "labels": [], "values": []},
        "speaker_notes": f"Dedicated diagram view for: {title}",
    }


def optimize_diagram_placement(slide_plan):
    """
    Post-process slide plan to defer diagrams from overcrowded slides to later slides.

    If no suitable slide is available, inserts a dedicated diagram-only slide.
    """
    slides = slide_plan.get("slides", [])

    if not slides:
        return slide_plan

    # First pass: collect all diagrams that need to be deferred.
    deferred_diagrams = {}  # Maps slide index to deferred diagram

    for idx, slide in enumerate(slides):
        # Skip title slides - they handle diagrams differently.
        if slide.get("type") == "title":
            continue

        diagram = slide.get("diagram", "")
        has_valid_diagram = bool(diagram and is_valid_mermaid(diagram))

        if has_valid_diagram and _is_overcrowded_for_diagram(slide):
            m = _slide_metrics(slide)
            deferred_diagrams[idx] = diagram
            slides[idx]["diagram"] = ""
            print(
                f"  [optimizer] Slide {idx+1}: Deferring diagram "
                f"(bullets={m['num_bullets']}, chars={m['bullet_char_count']}, volume={m['content_volume']})"
            )

    # Second pass: place deferred diagrams on the next suitable slides.
    # Process in reverse order to handle index shifts safely.
    for original_idx in sorted(deferred_diagrams.keys(), reverse=True):
        deferred_diagram = deferred_diagrams[original_idx]

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
                    print(f"  [optimizer] Placed deferred diagram on slide {target_idx+1}")
                    placed = True
                    break

            target_idx += 1

        if not placed:
            source_slide = slides[original_idx] if original_idx < len(slides) else {}
            diagram_slide = _make_diagram_only_slide(source_slide, deferred_diagram)
            insert_at = min(original_idx + 1, len(slides))
            slides.insert(insert_at, diagram_slide)
            print(
                f"  [optimizer] Inserted dedicated diagram slide at {insert_at+1} "
                f"for deferred diagram from slide {original_idx+1}"
            )

    return slide_plan
