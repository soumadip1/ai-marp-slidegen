"""
Global configuration and constants for the Marp presentation generator.

This module handles:
- Loading environment variables (API keys)
- Setting up output directories
- Defining constants and valid Mermaid diagram types
"""

import os
from pathlib import Path
from dotenv import load_dotenv

SOURCE_ROOT = Path(__file__).resolve().parent.parent


def _resolve_runtime_base_dir() -> Path:
    """
    Choose the runtime base directory for config and generated output.

    Priority:
    1. Current working directory when it contains a .env file
    2. Source tree root when running directly from the repo and it contains a .env
    3. Current working directory as a final fallback
    """
    cwd = Path.cwd()
    cwd_env = cwd / ".env"
    source_env = SOURCE_ROOT / ".env"

    if cwd_env.exists():
        return cwd

    if source_env.exists():
        return SOURCE_ROOT

    return cwd


BASE_DIR = _resolve_runtime_base_dir()

# Load environment variables from the runtime base directory.
load_dotenv(dotenv_path=BASE_DIR / ".env")

# ========== API KEYS ==========
# These should be set in .env file or as environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
UNSPLASH_API_KEY = os.getenv("UNSPLASH_API_KEY", "")

# ========== OUTPUT DIRECTORIES ==========
# Write output relative to the resolved runtime base directory.
PPT_DIR = BASE_DIR / "PPT"
ASSETS_DIR = BASE_DIR / "assets"

# Create directories if they don't exist
PPT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# ========== CONSTANTS ==========
# Valid first tokens/keywords for Mermaid diagram types
MERMAID_VALID_STARTERS = (
    "graph", "flowchart", "sequencediagram", "classdiagram",
    "statediagram", "erdiagram", "gantt", "pie", "journey",
    "gitgraph", "mindmap", "timeline", "xychart",
)

# Common stopwords used in text processing
STOPWORDS = {
    "the", "and", "of", "on", "in", "for", "a", "an", "to", "with", 
    "by", "is", "are", "as", "be", "its", "our", "this", "that"
}

# Image API configuration
IMAGE_FETCH_TIMEOUT = 10  # seconds for API calls
IMAGE_DOWNLOAD_TIMEOUT = 15  # seconds for downloading actual image
DEFAULT_IMAGE_DIMENSIONS = (1600, 900)  # width x height for fallback images
