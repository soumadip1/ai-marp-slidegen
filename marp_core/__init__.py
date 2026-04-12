"""
Marp Presentation Generator - Core Module

A modular presentation generation system that creates professional PowerPoint
presentations from text topics using GPT-4 and Marp markdown.

Packages:
- config: Global configuration and constants
- image: Stock image downloading and querying
- slide: Slide plan generation and rendering
- utils: Text utilities and validators
- export: Presentation export functionality
- io: File I/O operations

Usage:
    from marp_core.slide.generator import generate_slide_plan
    from marp_core.slide.renderer import render_marpit_markdown
    from marp_core.io.file import save_markdown
    from marp_core.export.marp import export_slides
"""

__version__ = "2.0.0"
__author__ = "Marp Generator Team"
