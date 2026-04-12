"""
Text processing and transformation utilities.

Functions for sanitizing, cleaning, and converting text formats.
"""

import re


def sanitize_text(value):
    """
    Sanitize and trim text by removing leading/trailing whitespace.
    
    Args:
        value (any): Value to sanitize (converted to string)
    
    Returns:
        str: Trimmed string, or empty string if value is None or falsy
    
    Description:
        Safe text cleaning function that handles None/empty values gracefully.
        Used throughout to clean JSON-extracted text before rendering in slides.
    """
    # Return empty string for None or falsy values
    if not value:
        return ""
    # Convert to string and trim whitespace
    return str(value).strip()


def camelcase_to_spaces(text):
    """
    Convert CamelCase text to space-separated words.
    
    Args:
        text (str): CamelCase text to convert
    
    Returns:
        str: Space-separated text (e.g., 'OilPriceRise' -> 'Oil Price Rise')
    
    Description:
        Uses regex to insert spaces before uppercase letters, making CamelCase readable.
        Used as fallback when diagram node IDs lack bracket labels.
    """
    # Insert space before uppercase letters that follow lowercase letters
    result = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    return result
