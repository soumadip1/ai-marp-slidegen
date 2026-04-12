"""
Image fetching from multiple stock image APIs with fallback chain.

Downloads images from Unsplash, Pexels, or picsum.photos with automatic fallback.
"""

import urllib.request
import time
from pathlib import Path
import requests

from ..config import PEXELS_API_KEY, UNSPLASH_API_KEY, ASSETS_DIR, IMAGE_FETCH_TIMEOUT, IMAGE_DOWNLOAD_TIMEOUT
from .query_generator import choose_stock_image_query


def _fetch_pexels(query, filename):
    """
    Fetch an image from Pexels API using the search query.
    
    Args:
        query (str): Search query for the image
        filename (Path or str): Full path where to save the downloaded image
    
    Returns:
        str: Path to the saved image file on success, None on any failure
    
    Description:
        Uses Pexels API v1 to search for images matching the query.
        Downloads the first high-quality result (large2x format).
        Returns None if API key is missing, no results found, or network error occurs.
    """
    # Return early if API key not configured
    if not PEXELS_API_KEY:
        return None
    
    api_url = "https://api.pexels.com/v1/search"
    # Set search parameters: 1 result, landscape mode, high resolution
    params = {"query": query, "per_page": 1, "orientation": "landscape", "size": "large"}
    # Include API key in Authorization header
    headers = {"Authorization": PEXELS_API_KEY}
    
    try:
        # Call Pexels API with timeout to prevent hanging
        response = requests.get(api_url, params=params, headers=headers, timeout=IMAGE_FETCH_TIMEOUT)
        
        # Check if API call was successful (HTTP 200)
        if response.status_code == 200:
            data = response.json()
            photos = data.get("photos", [])
            # No images found for this query
            if not photos:
                return None
            
            # Extract the high-resolution image URL from the first result
            img_url = photos[0]["src"]["large2x"]
            # Download the actual image
            img_response = requests.get(img_url, timeout=IMAGE_DOWNLOAD_TIMEOUT)
            # Write image to file if download successful
            if img_response.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(img_response.content)
                return str(filename)
        return None
    except Exception:
        # Silently fail and return None (will trigger fallback image sources)
        return None


def _fetch_unsplash(query, filename):
    """
    Fetch an image from Unsplash API using the search query.
    
    Args:
        query (str): Search query for the image
        filename (Path or str): Full path where to save the downloaded image
    
    Returns:
        str: Path to the saved image file on success, None on any failure
    
    Description:
        Uses Unsplash API to search for images matching the query.
        Downloads the first result in 'regular' resolution.
        Returns None if API key is missing, no results found, or network error occurs.
    """
    # Return early if API key not configured
    if not UNSPLASH_API_KEY:
        return None
    
    api_url = "https://api.unsplash.com/search/photos"
    # Set search parameters: 1 result, landscape orientation
    params = {"query": query, "per_page": 1, "orientation": "landscape"}
    # Unsplash requires Client-ID in Authorization header (not Bearer token)
    headers = {"Authorization": f"Client-ID {UNSPLASH_API_KEY}"}
    
    try:
        # Call Unsplash API with timeout to prevent hanging
        response = requests.get(api_url, params=params, headers=headers, timeout=IMAGE_FETCH_TIMEOUT)
        
        # Check if API call was successful (HTTP 200)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            # No images found for this query
            if not results:
                return None
            
            # Extract the regular resolution image URL from the first result
            img_url = results[0]["urls"]["regular"]
            # Download the actual image
            img_response = requests.get(img_url, timeout=IMAGE_DOWNLOAD_TIMEOUT)
            # Write image to file if download successful
            if img_response.status_code == 200:
                with open(filename, "wb") as f:
                    f.write(img_response.content)
                return str(filename)
        return None
    except Exception:
        # Silently fail and return None (will trigger fallback image sources)
        return None


def _fetch_picsum(slide_index, filename, topic=""):
    """
    Fetch a fallback image from picsum.photos (deterministic placeholder service).
    
    Args:
        slide_index (int): Index of the slide (used for seeding deterministic images)
        filename (Path or str): Full path where to save the downloaded image
        topic (str, optional): The topic being presented. Used to vary images across topics.
    
    Returns:
        str: Path to the saved image file on success, None on any failure
    
    Description:
        Uses picsum.photos seeded service for deterministic placeholder images.
        No authentication required. Always reachable as fallback.
        Includes topic in seed to ensure different topics get different cached images.
    """
    # Create deterministic seed including topic to differentiate across presentations
    seed = f"{topic.lower().replace(' ', '_')}_{slide_index}" if topic else str(slide_index)
    # Build URL with fixed dimensions (1600x900 landscape)
    url = f"https://picsum.photos/seed/{seed}/1600/900"
    try:
        # Create request with browser user-agent to avoid blocking
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        # Download and save the image
        with urllib.request.urlopen(req, timeout=IMAGE_FETCH_TIMEOUT) as resp, open(filename, "wb") as f:
            f.write(resp.read())
        return str(filename)
    except Exception:
        # Silently fail - no other fallbacks available for images
        return None


def download_stock_image(query, slide_index, topic):
    """
    Download a stock image for a specific slide using multiple API sources with fallback.
    
    Args:
        query (str): Search query for the image
        slide_index (int): Index number of the slide (1-10)
        topic (str): The main topic being presented
    
    Returns:
        str: Relative path to downloaded image (e.g., "../assets/topic_name/slide_image_1.jpg")
        None: If all image sources fail
    
    Description:
        Tries image sources in order: Unsplash → Pexels → Picsum fallback.
        Creates topic-specific subdirectories to organize images by presentation.
        Prints status with source and timing information.
    """
    # Create topic-specific subdirectory to organize images by presentation
    topic_assets_dir = ASSETS_DIR / topic.lower().replace(" ", "_")
    topic_assets_dir.mkdir(parents=True, exist_ok=True)
    
    # Define local filename with slide index
    filename = topic_assets_dir / f"slide_image_{slide_index}.jpg"
    t = time.time()  # Start timer for performance tracking

    # Try Unsplash first (most reliable), then Pexels, then picsum fallback
    result = _fetch_unsplash(query, filename) if UNSPLASH_API_KEY else None
    source = "unsplash"
    
    # Fallback to Pexels if Unsplash failed or key not configured
    if not result:
        result = _fetch_pexels(query, filename)
        source = "pexels"
    
    # Final fallback to picsum.photos (always works, deterministic)
    if not result:
        result = _fetch_picsum(slide_index, filename, topic)
        source = "picsum"

    if result:
        elapsed = f"{time.time()-t:.1f}s"
        print(f"  [img {slide_index:02d}] {source.upper():8s} {elapsed:>6s}  Query: {query[:50]}")
        # Return path relative to PPT_DIR where markdown file is saved
        topic_folder = topic.lower().replace(" ", "_")
        return f"../assets/{topic_folder}/slide_image_{slide_index}.jpg"
    print(f"  [img {slide_index:02d}] FAILED")
    return None
