"""
Main orchestration module for the Marp Presentation Generator.

This is the primary entry point for generating presentations from topics.
It coordinates all the core modules to generate, render, and export presentations.

Workflow Overview:
1. Topic to PPT Flow:
   - User provides a topic string.
   - `marp_core.slide.generator` uses LLMs to create a structured JSON slide plan.
   - `marp_core.slide.renderer` fetches images (Unsplash/Pexels) and formats Marp Markdown.
   - `marp_core.io.file` persists the markdown to the local filesystem.
   - `marp_core.export.marp` invokes the Marp CLI to generate a .pptx file.

2. Markdown to PPT Flow:
   - User provides a path to an existing .md file.
   - The system validates the path and file type.
   - The file is passed directly to the Marp CLI for conversion.

Requirements:
   - Marp CLI must be installed and available in the system PATH.
   - Valid API keys for OpenAI (for generation) and Unsplash/Pexels (for images).
"""

import time
from pathlib import Path
from marp_core.config import PEXELS_API_KEY, UNSPLASH_API_KEY
from marp_core.slide.generator import generate_slide_plan
from marp_core.slide.renderer import render_marpit_markdown
from marp_core.io.file import save_markdown
from marp_core.export.marp import export_slides


def show_api_status():
    """
    Display the configured image API status before generation starts.

    Args:
        None

    Returns:
        None

    Description:
        Prints a short status report that tells the user which image providers
        are available in the current environment. This gives immediate feedback
        about whether the generator will use Unsplash, Pexels, or fall back to
        local placeholder sources.

    Features:
        - Confirms Unsplash configuration before rendering begins
        - Confirms Pexels configuration before rendering begins
        - Explains fallback behavior when an API key is missing
    """
    # Display API configuration status
    print("Checking image APIs...")

    if UNSPLASH_API_KEY:
        print("Unsplash API key found (will try first)")
    else:
        print("Unsplash API key not set, will skip Unsplash and try Pexels if available")

    if PEXELS_API_KEY:
        print("Pexels API key found")
    else:
        print("Pexels API key not set")

    print()


def topic_to_ppt():
    """
    Generate a presentation from an input topic and export it to PPTX.

    Args:
        None

    Returns:
        None

    Description:
        This is the interactive topic-to-deck workflow. It asks for a topic,
        builds a slide plan with the OpenAI-backed generator, renders Marp
        markdown with images, saves the markdown to disk, and exports the final
        deck to PowerPoint.

    Features:
        - Interactive topic prompt for quick deck creation
        - Full pipeline from slide plan to PPTX export
        - Timing output for each stage of the workflow
        - Debug output for generated Mermaid diagrams
    """
    show_api_status()

    # Get topic from user
    topic = input("Enter topic: ")
    if not topic.strip():
        print("Topic cannot be empty.")
        return

    # Get number of slides from user
    num_slides_input = input("Enter number of slides (default 16): ").strip()
    if num_slides_input:
        try:
            num_slides = int(num_slides_input)
            if num_slides < 1:
                print("Number of slides must be at least 1. Using default 16.")
                num_slides = 16
        except ValueError:
            print("Invalid number. Using default 16.")
            num_slides = 16
    else:
        num_slides = 16

    # Step 1: Generate slide plan from GPT-5.4-mini
    t0 = time.time()
    try:
        plan = generate_slide_plan(topic, num_slides)
    except Exception as err:
        print(f"Slide plan generation failed: {err}")
        print("Please check your OPENAI_API_KEY and try again.")
        return
    print(f"[{time.time()-t0:.1f}s] Slide plan generated ({len(plan.get('slides', []))} slides)")

    # Debug: show diagrams if any for troubleshooting diagram parsing
    for idx, slide in enumerate(plan.get('slides', []), 1):
        if slide.get('diagram'):
            diagram_text = slide['diagram']
            print(f"\n Slide {idx} full diagram:")
            print(f"  ---BEGIN---")
            print(diagram_text)
            print(f"  ---END---")

    # Step 2: Render markdown with downloaded images
    t1 = time.time()
    markdown = render_marpit_markdown(plan, topic)
    print(f"[{time.time()-t1:.1f}s] Markdown rendered (includes image downloads)")

    # Step 3: Save markdown to file
    t2 = time.time()
    file = save_markdown(topic, markdown)
    print(f"[{time.time()-t2:.1f}s] Markdown saved: {file}")

    # Step 4: Convert markdown to PowerPoint
    t3 = time.time()
    export_slides(file)
    print(f"[{time.time()-t3:.1f}s] PPTX export finished")

    # Print total execution time
    print(f"[{time.time()-t0:.1f}s] Total")


def markdown_to_ppt():
    """
    Convert an existing Marp markdown file to PPTX.

    Args:
        None

    Returns:
        None

    Description:
        This workflow converts a user-provided markdown file directly into a
        PowerPoint deck without regenerating slide content. It validates the
        path, checks that the file has an .md extension, and then passes the
        file to the Marp export step.

    Features:
        - Accepts an absolute or expanded markdown path from the user
        - Validates that the file exists before exporting
        - Rejects non-markdown inputs early
    """
    md_input = input("Enter full path to markdown file: ").strip().strip('"')
    if not md_input:
        print("Markdown file path cannot be empty.")
        return

    md_path = Path(md_input).expanduser()

    if not md_path.exists():
        print(f"Markdown file not found: {md_path}")
        return

    if md_path.suffix.lower() != ".md":
        print("Please provide a valid .md file.")
        return

    t0 = time.time()
    export_slides(str(md_path.resolve()))
    print(f"[{time.time()-t0:.1f}s] PPTX export finished")


def main():
    """
    Main entry point for the presentation generation workflow.

    Offers two flows:
    1. Topic to PPT
    2. Markdown file to PPT

    Returns:
        None
    """
    print("Choose conversion mode:")
    print("1. Topic to PPT")
    print("2. Markdown file to PPT")

    choice = input("Enter 1 or 2: ").strip().lower()

    if choice in {"1", "topic", "topic to ppt", "topic-to-ppt"}:
        topic_to_ppt()
    elif choice in {"2", "markdown", "markdown file to ppt", "markdown to ppt", "md"}:
        markdown_to_ppt()
    else:
        print("Invalid choice. Please restart and enter 1 or 2.")


if __name__ == "__main__":
    main()
