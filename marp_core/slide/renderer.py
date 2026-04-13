"""
Marp markdown rendering from slide plans.

Converts slide plan JSON to Marp-formatted markdown with images and content.
"""

import re
import time
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..utils.text import sanitize_text, camelcase_to_spaces
from ..utils.validators import is_valid_mermaid
from ..utils.mermaid import convert_mermaid_to_png
from ..image.query_generator import choose_stock_image_query
from ..image.fetcher import download_stock_image
from ..config import ASSETS_DIR


def _extract_mermaid_aliases(diagram):
    """
    Extract readable node labels from Mermaid diagram text.

    Args:
        diagram (str): Raw Mermaid source that may contain node definitions
            such as ``NodeId[Readable Label]``.

    Returns:
        dict: A mapping of Mermaid node IDs to sanitized display labels.

    Description:
        This helper scans each line of the Mermaid diagram and captures node
        declarations that include bracketed labels. Those labels are normalized
        before being stored so the renderer can produce human-friendly slide
        text later.

    Features:
        - Detects bracket-based node labels in flow-style Mermaid diagrams
        - Sanitizes labels before they are reused elsewhere
        - Ignores unrelated Mermaid syntax and non-node lines
    """
    aliases = {}

    for line in diagram.strip().split("\n"):
        for node_id, label in re.findall(r'([A-Za-z0-9_]+)\[([^\]]+)\]', line):
            aliases[node_id.strip()] = sanitize_text(label)

    return aliases


def _resolve_mermaid_node_label(node_text, aliases):
    """
    Convert a Mermaid node token into a readable label.

    Args:
        node_text (str): Raw Mermaid token extracted from an edge or node.
        aliases (dict): Mapping of Mermaid node IDs to display labels produced
            by ``_extract_mermaid_aliases``.

    Returns:
        str: A human-readable label for the node, or an empty string if no
        meaningful text can be derived.

    Description:
        The renderer uses this helper when turning Mermaid flows into plain
        markdown bullet points. It prefers an explicit bracket label, then a
        previously extracted alias, and finally a CamelCase-to-spaces fallback.

    Features:
        - Preserves explicit Mermaid labels when they are available
        - Reuses alias mappings for repeated node references
        - Falls back to readable CamelCase formatting for raw node IDs
    """
    node_text = sanitize_text(node_text)
    if not node_text:
        return ""

    bracket_match = re.search(r'\[([^\]]+)\]', node_text)
    if bracket_match:
        return sanitize_text(bracket_match.group(1))

    node_id = node_text.split("{")[0].split("(")[0].split("[")[0].strip()
    if node_id in aliases:
        return aliases[node_id]

    return camelcase_to_spaces(node_id)


def _build_closing_slide():
    """
    Build the fixed closing slide used at the end of every deck.

    Args:
        None

    Returns:
        str: Markdown content for a thank-you slide with a closing signature.

    Description:
        This helper centralizes the final slide text so the presentation ends
        with a consistent closing page. It keeps the closing content separate
        from the main rendering loop for clarity and reuse.

    Features:
        - Produces a consistent end slide for all generated presentations
        - Keeps the closing signature in one place
        - Returns ready-to-render Marp markdown
    """
    return "\n".join([
        "# THANK YOU",
        "",
        '<div style="width: 100%; margin-top: 3em; text-align: right; color: #555555; font-size: 0.8em;">- Richa Kumari &amp; Soumadip B</div>',
    ])


def render_marpit_markdown(slide_json, topic):
    """
    Convert slide plan JSON to Marp-formatted markdown with embedded images and content.
    
    Args:
        slide_json (dict): Complete slide plan with structure {title, slides: [{type, title, ...}, ...]}
        topic (str): The presentation topic (used for image correlation)
    
    Returns:
        str: Complete Marp markdown document ready for export to PowerPoint
    
    Description:
        Orchestrates the rendering pipeline:
        1. Sets up Marp metadata and CSS styling for professional appearance
        2. Generates image queries for each slide (topic-aware and parallel-downloaded)
        3. Parses slide content (diagrams, code, charts, bullets) into markdown
        4. Handles special content types (Mermaid diagrams with bracket label extraction,
           code blocks with syntax highlighting, charts with descriptions)
        5. Properly formats for Marp slide transitions and speaker notes
        
        Key Features:
        - Parallel image downloads using ThreadPoolExecutor for performance
        - Mermaid diagram parsing: extracts labels from [brackets], converts CamelCase to spaces
        - Diagram flow limitation: 5 flows per slide for readability
        - Chart descriptions: includes units/context for numeric data visualization
        - Title slide formatting: dark background with left image, large typography
        - Content slide formatting: right-side images at 35% width for balanced layout
        - Speaker notes: embedded in HTML comments for presenter view
    """
    # Initialize slides list with Marp configuration
    slides = []

    # Add Marp metadata and global configuration
    # Sets theme to "gaia" for professional look, enables pagination
    slides.append("---\nmarp: true\ntheme: gaia\npaginate: true\n---\n")
    
    # Add comprehensive CSS styling for all slide elements
    # Includes color scheme, typography, image positioning, code formatting
    # Optimized for 40% right-side images with adequate left content spacing
    slides.append("<style>\nsection { color: #1a1a1a; font-size: 28px; padding: 1.5rem 1.5rem 1.5rem 1.5rem; }\nh1 { font-size: 2.2em; line-height: 1.1; color: #0f4c81; word-break: break-word; margin-bottom: 0.3em; }\nh2 { font-size: 1.4em; line-height: 1.2; color: #125c9b; margin-bottom: 0.3em; }\nh4 { font-size: 1.3em; line-height: 1.2; color: #0f4c81; margin-bottom: 0.4em; }\nul { font-size: 1em; line-height: 1.6; padding-left: 1.2rem; margin-top: 0.5rem; }\nli { margin-bottom: 0.4rem; }\np { font-size: 1em; }\ntable { font-size: 0.75em; width: 55%; }\ntd { padding: 0.3em 0.5em; }\nth { padding: 0.4em 0.5em; }\nimg { max-width: 100%; height: auto; }\nimg[alt*=\"Diagram\"] { max-height: 56vh; max-width: 80%; width: auto; height: auto; object-fit: contain; margin: 1.2em auto; display: block; }\ndiv[style*=\"text-align: center\"] { display: flex; flex-direction: column; justify-content: center; align-items: center; width: 100%; }\ndiv[style*=\"text-align: center\"] img { display: block; margin: 0 auto; }\nsection.title-page { display: flex; flex-direction: column; justify-content: center; align-items: flex-start; color: white; padding: 2.5rem 3.5rem; }\nsection.title-page h1 { color: white; font-size: 2.4em; line-height: 1.15; margin-bottom: 0.5em; }\nsection.title-page h2 { color: #c8ddf0; font-size: 1.4em; font-weight: 400; }\nsection.content-full { display: flex; flex-direction: column; justify-content: center; padding: 2rem 3.5rem; }\nsection.content-full h4 { font-size: 1.5em; margin-bottom: 0.6em; }\nsection.content-full ul { font-size: 1.1em; line-height: 1.7; }\nsection.content-full li { margin-bottom: 0.5rem; }\nsection.closing-slide { display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 2rem 3.5rem; }\nsection.closing-slide h1 { text-align: center; width: 100%; font-size: 2.5em; font-weight: 700; }\npre { background-color: #f5f5f5; padding: 1rem; border-radius: 4px; font-size: 0.85em; width: 55%; color: #1a1a1a; }\ncode { font-family: 'Courier New', monospace; color: #1a1a1a; }\nblockquote { border-left: 4px solid #0f4c81; padding-left: 1rem; color: #1a1a1a; }\n</style>\n")

    # ========== IMAGE DOWNLOAD ORCHESTRATION ==========
    # Pre-compute all image queries and download in parallel for better performance
    slides_data = slide_json.get("slides", [])
    queries = {}
    
    # Generate image search query for each slide
    for idx, slide in enumerate(slides_data, start=1):
        slide_title = sanitize_text(slide.get("title"))
        slide_type = slide.get("type", "content")
        iq = sanitize_text(slide.get("image_query"))
        
        # Use provided query from GPT, or generate contextual one including topic
        if not iq:
            iq = choose_stock_image_query(slide_title or slide_json.get("title", ""), slide_type, topic)
        queries[idx] = iq

    closing_slide_index = len(slides_data) + 1
    queries[closing_slide_index] = choose_stock_image_query("thank you", "content", topic)

    # Display image queries for debugging image relevance
    print(f"  Image queries for {len(queries)} slides:")
    for idx, query in queries.items():
        print(f"    Slide {idx}: {query}")

    # Download images in parallel to improve performance
    # ThreadPoolExecutor allows multiple API requests to Unsplash/Pexels simultaneously
    print(f"  Downloading {len(queries)} images in parallel...")
    img_t = time.time()
    image_paths = {}
    with ThreadPoolExecutor(max_workers=len(queries)) as executor:
        # Map futures to slide indices for correlation
        future_map = {executor.submit(download_stock_image, q, i, topic): i for i, q in queries.items()}
        # Collect results as they complete (order doesn't matter due to mapping)
        for future in as_completed(future_map):
            image_paths[future_map[future]] = future.result()
    print(f"  [images] completed in {time.time()-img_t:.1f}s")

    # ========== SLIDE RENDERING LOOP ==========
    # Iterate through each slide and convert JSON to Marp markdown
    for idx, slide in enumerate(slides_data, start=1):
        # Extract slide metadata with sanitization to prevent markdown injection
        title = sanitize_text(slide.get("title"))
        subtitle = sanitize_text(slide.get("subtitle"))
        icon = sanitize_text(slide.get("icon"))
        bullets = slide.get("bullets") or []
        slide_type = slide.get("type", "content")

        # Get downloaded image path for this slide (may be None if download failed)
        image_path = image_paths.get(idx)
        
        # Extract optional rich content
        diagram = sanitize_text(slide.get("diagram"))
        code = slide.get("code") or {}
        chart = slide.get("chart") or {}
        notes = sanitize_text(slide.get("speaker_notes"))

        slide_lines = []
        
        # ========== TITLE SLIDE FORMATTING ==========
        if slide_type == "title":
            # Use Marp directives for styling (single underscore prefix for local directives)
            slide_lines.append("<!-- _class: title-page -->")
            slide_lines.append("<!-- _backgroundColor: #0f4c81 -->")
            
            # Add title slide image if available (positioned left, covers background)
            if image_path:
                slide_lines.append(f"![bg left:45% cover]({image_path})")
            
            slide_lines.append("")
            # Title with emoji icon (icon comes from GPT)
            slide_lines.append(f"# {icon} {title}".strip())
            
            # Subtitle in lighter color for visual hierarchy
            if subtitle:
                slide_lines.append(f"## {subtitle}")
        
        # ========== CONTENT SLIDE FORMATTING ==========
        else:
            # Check if this slide will have a diagram - use already-extracted diagram variable
            has_diagram = diagram and is_valid_mermaid(diagram)
            
            # Add background image with appropriate sizing based on content
            if image_path:
                if has_diagram:
                    # Diagram slide - use 30% background image on right
                    # Add HTML div to center content in the remaining left space
                    slide_lines.append(f"![bg right:30% cover]({image_path})")
                    slide_lines.append("<div style='display: flex; flex-direction: column; justify-content: center; align-items: center; width: 100%; text-align: center;'>")
                else:
                    # Regular content slide - use standard background image (40% width)
                    slide_lines.append(f"![bg right:40% cover]({image_path})")
            else:
                # If no image, use full-width content layout
                slide_lines.append("<!-- _class: content-full -->")
            
            slide_lines.append("")
            # Content slide heading with icon
            slide_lines.append(f"#### {icon} {title}".strip())

            # ========== BULLET POINTS RENDERING ==========
            if bullets:
                slide_lines.append("")
                # Limit to 4 bullets for readability and slide space
                for bullet in bullets[:4]:
                    bullet_text = sanitize_text(bullet)
                    if bullet_text:
                        # Standard markdown bullet format
                        slide_lines.append(f"- {bullet_text}")

            # ========== MERMAID DIAGRAM PARSING ==========
            # Note: Diagram placement is already optimized by diagram_optimizer
            # which moves diagrams from overcrowded slides to the next slide.
            # Here we just render diagrams that are present, or skip if slide is still too full.
            num_bullets = min(len(bullets), 4)  # Max 4 bullets are rendered
            has_code = bool(code.get("content"))
            
            # Calculate content occupancy
            if diagram and is_valid_mermaid(diagram):
                # Slide has a diagram - use it as main content
                content_volume = num_bullets
            else:
                # No diagram - count code and other content
                content_volume = num_bullets + (2 if has_code else 0) + (1 if subtitle else 0)
            
            # Last-resort skip: optimizer should already defer crowded slides.
            # Keep this threshold very high to avoid silently dropping diagrams.
            should_skip_diagram = content_volume >= 7 and num_bullets >= 4
            
            if diagram and is_valid_mermaid(diagram) and not should_skip_diagram:
                slide_lines.append("")
                
                # Create topic-specific subdirectory for diagram images
                topic_diagrams_dir = ASSETS_DIR / topic.lower().replace(" ", "_") / "diagrams"
                topic_diagrams_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate unique filename for this slide's diagram
                diagram_filename = topic_diagrams_dir / f"diagram_slide_{idx}.png"
                
                # Try to convert Mermaid code to PNG image
                diagram_image_path = convert_mermaid_to_png(diagram, str(diagram_filename))
                
                if diagram_image_path:
                    # Conversion successful - embed image as base64 data URI
                    # This embeds the image directly in the markdown, avoiding file path issues
                    try:
                        with open(diagram_image_path, 'rb') as f:
                            image_data = f.read()
                        
                        # Encode to base64
                        base64_data = base64.b64encode(image_data).decode('utf-8')
                        data_uri = f"data:image/png;base64,{base64_data}"
                        
                        # Dynamically size diagrams based on text density to avoid slide clipping.
                        if num_bullets >= 3:
                            diagram_width = 340
                        elif num_bullets == 2:
                            diagram_width = 400
                        elif num_bullets == 1:
                            diagram_width = 460
                        else:
                            diagram_width = 520

                        # When there is a right-side background image, reserve more space.
                        if image_path:
                            diagram_width = min(diagram_width, 460)

                        slide_lines.append(f'![Diagram w:{diagram_width}]({data_uri})')
                        print(f"  [diagram {idx:02d}] Rendered as image (embedded base64, centered)")
                    except Exception as embed_err:
                        print(f"  [diagram {idx:02d}] Warning: Could not embed as base64: {embed_err}")
                        # Fallback to file path
                        topic_folder = topic.lower().replace(" ", "_")
                        relative_path = f"../assets/{topic_folder}/diagrams/diagram_slide_{idx}.png"
                        slide_lines.append(f"![Diagram w:420]({relative_path})")
                        print(f"  [diagram {idx:02d}] Rendered as file reference (fallback)")
                else:
                    # Fallback: render as text-based flow map with bullet points
                    slide_lines.append("**Flow Map:**")
                    slide_lines.append("")
                    alias_map = _extract_mermaid_aliases(diagram)
                    
                    # Parse Mermaid diagram to extract relationships
                    # Format expected: NodeId[Label] --> NodeId2[Label2]
                    diagram_lines = diagram.strip().split('\n')
                    processed_lines = []
                    
                    for line in diagram_lines:
                        line = line.strip()
                        # Skip lines that are not relationships (empty, comments, headers)
                        if not line or line.startswith('graph') or line.startswith('flowchart') or line.startswith('---'):
                            continue
                        
                        # Look for arrow pattern indicating a relationship/flow
                        if '-->' in line:
                            parts = line.split('-->')
                            if len(parts) == 2:
                                source = parts[0].strip()
                                dest = parts[1].strip()

                                source_text = _resolve_mermaid_node_label(source, alias_map)
                                dest_text = _resolve_mermaid_node_label(dest, alias_map)

                                if source_text and dest_text and source_text not in ('graph', 'flowchart') and dest_text not in ('graph', 'flowchart'):
                                    processed_lines.append(f"- {source_text} -> {dest_text}")
                    
                    # Add processed lines to slide, limiting to 5 flows for readability
                    if processed_lines:
                        for pline in processed_lines[:5]:
                            slide_lines.append(pline)
                    else:
                        # Fallback message if diagram parsing returned no flows
                        slide_lines.append("*(Diagram content available in full presentation)*")
                
                # Close the centering div if it was opened for a diagram with bg image
                if image_path and diagram and is_valid_mermaid(diagram):
                    slide_lines.append("</div>")
            
            elif diagram and is_valid_mermaid(diagram) and should_skip_diagram:
                # Slide is too full - diagram was supposed to be moved by optimizer
                # but check remained due to late content changes
                # Skip diagram entirely (don't render as text) to prevent overflow
                print(f"  [diagram {idx:02d}] Skipped (content volume too high after optimization)")


            # ========== CODE BLOCK RENDERING ==========
            # Skip code rendering if a diagram is present (diagrams take priority for visual clarity)
            # This prevents slides from being too crowded with both code AND diagrams
            has_diagram_content = diagram and is_valid_mermaid(diagram) and not should_skip_diagram
            
            if code.get("content") and not has_diagram_content:
                # Only show code if no diagram is being displayed
                slide_lines.append("")
                # Add syntax highlighting language specifier (python, javascript, etc.)
                slide_lines.append(f"```{sanitize_text(code.get('language'))}")
                # Split code into lines to preserve formatting
                slide_lines.extend(sanitize_text(code.get("content")).split('\n'))
                slide_lines.append("```")

            # ========== CHART/TABLE RENDERING ==========
            if chart.get("type") and chart.get("labels") and chart.get("values"):
                slide_lines.append("")
                # Chart type header (capitalized)
                chart_type = sanitize_text(chart.get('type')).capitalize()
                slide_lines.append(f"### {chart_type}")
                
                # Add description/units for data clarity
                # Example: "Visitor Count (thousands)" or "Revenue (millions USD)"
                chart_description = sanitize_text(chart.get('description', ''))
                if chart_description:
                    slide_lines.append(f"*{chart_description}*")
                
                slide_lines.append("")
                
                # Create markdown table with labels as headers and values as data row
                labels = chart.get("labels", [])
                values = chart.get("values", [])
                if len(labels) == len(values):
                    # Header row: | Label1 | Label2 | ...
                    slide_lines.append("| " + " | ".join(labels) + " |")
                    # Separator row: | --- | --- | ...
                    slide_lines.append("|" + " --- |" * len(labels))
                    # Data row: | Value1 | Value2 | ...
                    slide_lines.append("| " + " | ".join(str(v) for v in values) + " |")

        # ========== SPEAKER NOTES ==========
        # Add speaker notes as HTML comments (appears in presenter view during presentation)
        if notes:
            slide_lines.append(f"\n<!-- {notes} -->")

        # Join slide lines and append to presentation
        slides.append("\n".join(slide_lines))

    # Add a fixed closing slide to generated topic-based presentations.
    closing_slide = ["<!-- _class: closing-slide -->"]
    closing_image_path = image_paths.get(closing_slide_index)
    if closing_image_path:
        closing_slide.append(f"![bg right:40% cover]({closing_image_path})")
    closing_slide.append("")
    closing_slide.append(_build_closing_slide())
    slides.append("\n".join(closing_slide))

    # ========== FINAL SLIDE ASSEMBLY ==========
    # Join all slides with Marp slide separator (---)
    # Keep frontmatter and style block separate, then join remaining slides
    # Note: No trailing --- to prevent creation of empty slide at end
    all_slides = slides[:2]  # frontmatter + style block (keep as-is)
    all_slides.append("\n---\n".join(slides[2:]))  # Join remaining slides with separator
    return "\n".join(all_slides)
