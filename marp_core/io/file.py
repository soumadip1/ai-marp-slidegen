"""
File system operations for saving and managing presentation files.

Functions for writing markdown and other file operations.
"""

from ..config import PPT_DIR


def save_markdown(topic, markdown):
    """
    Save markdown content to a file in the PPT output directory.
    
    Args:
        topic (str): The presentation topic
        markdown (str): Complete markdown content for the presentation
    
    Returns:
        str: Absolute path to the saved markdown file
    
    Description:
        Creates filename from topic (lowercase, spaces to underscores).
        Saves to PPT_DIR for organization alongside generated PowerPoint files.
    """
    # Generate filename from topic: "My Topic" -> "my_topic.md"
    filename = PPT_DIR / (topic.lower().replace(" ", "_") + ".md")
    # Write markdown content to file
    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown)
    return str(filename)
