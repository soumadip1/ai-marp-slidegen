"""
Diagram optimization and deferral for slide overflow prevention.

Post-processes slide plans to move diagrams from content-heavy slides to the next slide.
"""

from ..utils.validators import is_valid_mermaid


def optimize_diagram_placement(slide_plan):
    """
    Post-process slide plan to defer diagrams from overcrowded slides to the next slide.
    
    Args:
        slide_plan (dict): Slide plan with structure {title, slides: [{type, title, bullets, diagram, ...}, ...]}
    
    Returns:
        dict: Modified slide plan with diagrams moved to accommodate slide content
    
    Description:
        Analyzes each slide's content volume (bullets, code, subtitle).
        If a slide has 3+ bullets AND a diagram, moves the diagram to the next slide.
        This prevents slide overflow by ensuring diagrams get dedicated space.
        Handles cascading: diagrams can be deferred multiple times if needed.
        Last slide diagrams that can't be deferred are removed.
        
    Features:
        - Calculates content occupancy for each slide
        - Intelligently defers diagrams without losing them
        - Prevents multiple diagrams from stacking on one slide
        - Maintains presentation flow and readability
    """
    slides = slide_plan.get("slides", [])
    
    if not slides:
        return slide_plan
    
    # First pass: collect all diagrams that need to be deferred
    deferred_diagrams = {}  # Maps slide index to deferred diagram
    
    for idx, slide in enumerate(slides):
        # Skip title slides - they handle diagrams differently
        if slide.get("type") == "title":
            continue
        
        slide_type = slide.get("type", "content")
        bullets = slide.get("bullets") or []
        code = slide.get("code") or {}
        diagram = slide.get("diagram", "")
        subtitle = slide.get("subtitle", "")
        
        # Calculate content volume
        num_bullets = len(bullets)
        has_code = bool(code.get("content"))
        has_subtitle = bool(subtitle.strip())
        
        # Content volume calculation:
        # - Each bullet: 1 unit
        # - Code block: 2 units
        # - Subtitle: 1 unit
        content_volume = num_bullets + (2 if has_code else 0) + (1 if has_subtitle else 0)
        
        # Check if slide is too crowded
        # Condition: 3+ bullets AND content_volume >= 5 AND has a valid diagram
        is_overcrowded = (num_bullets >= 3 and content_volume >= 5)
        has_valid_diagram = diagram and is_valid_mermaid(diagram)
        
        # If overcrowded and has diagram, mark diagram for deferral
        if is_overcrowded and has_valid_diagram:
            deferred_diagrams[idx] = diagram
            # Clear diagram from current slide
            slides[idx]["diagram"] = ""
            print(f"  [optimizer] Slide {idx+1}: Deferring diagram (content volume: {content_volume}) to next slide")
    
    # Second pass: place deferred diagrams on next available slides
    # Process in reverse order to handle cascading correctly
    for original_idx in sorted(deferred_diagrams.keys(), reverse=True):
        deferred_diagram = deferred_diagrams[original_idx]
        
        # Find next available slide (skip title slides)
        target_idx = original_idx + 1
        placed = False
        
        while target_idx < len(slides):
            target_slide = slides[target_idx]
            
            # Only place on content slides
            if target_slide.get("type") != "title":
                # Check if target slide already has a diagram
                existing_diagram = target_slide.get("diagram", "")
                
                # Only place if target slide has no diagram
                if not existing_diagram or not is_valid_mermaid(existing_diagram):
                    # Target slide is available - place diagram here
                    slides[target_idx]["diagram"] = deferred_diagram
                    print(f"  [optimizer] Placed deferred diagram on slide {target_idx+1}")
                    placed = True
                    break
            
            target_idx += 1
        
        # If no available slide found, discard the diagram
        if not placed:
            print(f"  [optimizer] Warning: Could not place deferred diagram from slide {original_idx+1} - discarding")
    
    return slide_plan
