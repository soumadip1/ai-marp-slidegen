"""
Image query generation for stock image APIs.

Functions for generating optimized search queries based on slide content and topic.
"""

import re
from ..utils.text import sanitize_text
from ..config import STOPWORDS


def choose_stock_image_query(title, slide_type, topic=""):
    """
    Generate a search query for stock images based on slide title and topic context.
    
    Args:
        title (str): The slide title to extract keywords from
        slide_type (str): The type of slide (e.g., 'title', 'content', 'diagram')
        topic (str, optional): The main topic being presented. Defaults to empty string.
    
    Returns:
        str: A space-separated string of 2-4 keywords for image search API
    
    Description:
        Extracts keywords from the topic first (prioritized), then from the slide title.
        Removes common stopwords to keep only meaningful terms. Falls back to generic
        keywords if no meaningful terms are extracted.
    """
    title = sanitize_text(title).lower() if isinstance(title, str) else ""
    topic = sanitize_text(topic).lower() if isinstance(topic, str) else ""
    
    # Extract keywords from topic, prioritizing it for relevance
    if topic:
        topic_tokens = re.findall(r"[a-z0-9]+", topic)
        topic_keywords = [t for t in topic_tokens if t not in STOPWORDS][:2]
    else:
        topic_keywords = []
    
    # Extract keywords from slide title
    tokens = re.findall(r"[a-z0-9]+", title)
    title_keywords = [t for t in tokens if t not in STOPWORDS]

    # Combine topic + title keywords, prioritizing topic
    all_keywords = topic_keywords + title_keywords
    
    # Fallback to generic keywords if nothing meaningful found
    if not all_keywords:
        all_keywords = ["travel", "destination", "landscape"]

    return " ".join(all_keywords[:4])
