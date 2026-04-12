"""
Validation functions for checking content types and formats.

Functions for validating Mermaid diagrams, slide content, etc.
"""

from .text import sanitize_text
from ..config import MERMAID_VALID_STARTERS


def is_valid_mermaid(content):
    """
    Validate if content is valid Mermaid diagram syntax.
    
    Args:
        content (str): Text content to validate
    
    Returns:
        bool: True if content starts with a valid Mermaid diagram keyword and has sufficient content, False otherwise
    
    Description:
        Checks if the first non-whitespace token matches a recognized Mermaid diagram type.
        Also validates that the content is substantial enough (has multiple lines or sufficient nodes)
        to avoid rendering gibberish/corrupted images from incomplete diagrams.
        Valid types include graph, flowchart, sequenceDiagram, classDiagram, etc.
    """
    if not content or not content.strip():
        return False
    
    # Extract first token (word) from content, converting to lowercase
    first_token = content.strip().split()[0].lower() if content.strip() else ""
    
    # Check if first token is a recognized Mermaid diagram starter
    if first_token not in MERMAID_VALID_STARTERS:
        return False
    
    # Additional validation: ensure diagram has enough content
    # Must have at least 2 lines (type declaration + at least one node/relationship)
    # or contain an arrow which indicates relationships
    lines = [line.strip() for line in content.strip().split('\n') if line.strip()]
    
    # Need at least 2 lines of content
    if len(lines) < 2:
        return False
    
    # For flowcharts/graphs, must contain an arrow (-->) or brackets/parentheses (node definition)
    content_lower = content.lower()
    has_structure = '-->' in content or '[]' in content or '()' in content or '{}' in content or '[' in content
    
    # Require some actual structure, not just the diagram type declaration
    if not has_structure:
        return False
    
    return True
