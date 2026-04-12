"""
Marp CLI integration for exporting presentations to PowerPoint.

Functions for invoking the Marp CLI tool to convert markdown to PPTX.
"""

import os
import shutil
import subprocess
from pathlib import Path


def export_slides(md_file):
    """
    Convert markdown file to PowerPoint (.pptx) using Marp CLI.
    
    Args:
        md_file (str): Path to the markdown file to convert
    
    Returns:
        None: (prints status to console)
    
    Description:
        Invokes Marp CLI to convert Marp markdown to PowerPoint format.
        Handles Windows-specific Node.js execution nuances.
        Falls back through multiple methods if preferred not found.
        Requires: npm install -g @marp-team/marp-cli
    """
    # Resolve to absolute path for subprocess execution
    md_path = Path(md_file).resolve()
    # Build Marp CLI arguments: convert to PPTX, allow local files, set timeout
    marp_args = [str(md_path), "--pptx", "--allow-local-files", "--timeout=120000"]

    if os.name == "nt":  # Windows-specific handling
        # Try to invoke Node.js + marp-cli.js directly (bypasses .CMD wrapper issues)
        node_exe = shutil.which("node")
        appdata = Path(os.environ.get("APPDATA", ""))
        marp_js = appdata / "npm" / "node_modules" / "@marp-team" / "marp-cli" / "marp-cli.js"

        if node_exe and marp_js.exists():
            # Use Node.js to run marp CLI script directly
            cmd = [node_exe, str(marp_js)] + marp_args
        else:
            # Fallback: resolve the installed Marp CLI binary directly.
            # Avoid shell=True on Windows because the wrapper can linger after export.
            marp_bin = shutil.which("marp")
            if not marp_bin:
                print("Marp CLI not found. Install it with: npm install -g @marp-team/marp-cli")
                return
            cmd = [marp_bin] + marp_args
    else:  # Unix/Linux/Mac
        cmd = ["marp"] + marp_args

    try:
        # Execute Marp conversion in the markdown file's directory
        subprocess.run(
            cmd,
            check=True,
            cwd=str(md_path.parent),
            shell=False,
            timeout=180,
        )
        print("PPTX created:", md_path.with_suffix(".pptx"))
    except subprocess.CalledProcessError as e:
        print("Marp CLI failed to export slides:", e)
        print("Ensure Marp CLI is installed and available in PATH.")
    except subprocess.TimeoutExpired:
        print("Marp CLI timed out while exporting slides.")
        print("The PPTX may have been created, but the Marp process did not exit in time.")
    except FileNotFoundError:
        print("Marp CLI not found. Install it with: npm install -g @marp-team/marp-cli")
