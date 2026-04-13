"""
Mermaid diagram conversion utilities.

Functions for converting Mermaid diagram code to PNG images for embedding in slides.
"""

import subprocess
import tempfile
import os
import time
import shutil
from pathlib import Path


def _resolve_mmdc_binary():
    """
    Resolve the Mermaid CLI executable path in a portable way.

    Resolution order:
    1. PATH lookup (`mmdc`, including Windows executable variants)
    2. npm global prefix lookup (`npm prefix -g`)
    3. Common npm global bin locations for the current user/profile
    """
    # 1) PATH-based resolution (works when npm global bin is in PATH)
    # Keep Windows to executable wrappers only; .ps1 requires PowerShell host.
    path_candidates = ["mmdc", "mmdc.cmd", "mmdc.exe", "mmdc.bat"]
    for candidate in path_candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    # 2) npm prefix-based resolution (works when npm is available but PATH isn't updated).
    npm_bin_candidates = []
    npm_exe = shutil.which("npm")
    if npm_exe:
        try:
            npm_prefix = subprocess.run(
                [npm_exe, "prefix", "-g"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            ).stdout.strip()
            if npm_prefix:
                prefix_path = Path(npm_prefix)
                if os.name == "nt":
                    npm_bin_candidates.extend(
                        [
                            prefix_path / "mmdc.cmd",
                            prefix_path / "mmdc.bat",
                        ]
                    )
                else:
                    npm_bin_candidates.append(prefix_path / "bin" / "mmdc")
        except Exception:
            # Ignore npm probing failures and continue with filesystem fallbacks.
            pass

    for candidate in npm_bin_candidates:
        if candidate.exists():
            return str(candidate)

    # 3) Known npm global bin locations (derived dynamically, no hardcoded usernames)
    disk_candidates = []

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            disk_candidates.extend(
                [
                    Path(appdata) / "npm" / "mmdc.cmd",
                    Path(appdata) / "npm" / "mmdc.bat",
                ]
            )

        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            disk_candidates.extend(
                [
                    Path(userprofile) / "AppData" / "Roaming" / "npm" / "mmdc.cmd",
                    Path(userprofile) / "AppData" / "Roaming" / "npm" / "mmdc.bat",
                ]
            )
    else:
        home = Path.home()
        disk_candidates.extend(
            [
                home / ".npm-global" / "bin" / "mmdc",
                home / ".local" / "bin" / "mmdc",
                Path("/usr/local/bin/mmdc"),
                Path("/opt/homebrew/bin/mmdc"),
            ]
        )

    for candidate in disk_candidates:
        if candidate.exists():
            return str(candidate)

    return None


def convert_mermaid_to_png(mermaid_code, output_path, timeout=30):
    """
    Convert Mermaid diagram code to PNG image using mermaid-cli.

    Args:
        mermaid_code (str): Raw Mermaid diagram syntax (e.g., flowchart, sequence diagram)
        output_path (str or Path): Full path where to save the PNG file
        timeout (int, optional): Timeout in seconds for the conversion. Defaults to 30.

    Returns:
        str: Path to the created PNG file on success, None if conversion fails

    Description:
        Uses the @mermaid-js/mermaid-cli (mmdc) binary to render Mermaid diagrams
        as PNG images. This allows complex diagrams (flowcharts, sequence, class, etc.)
        to be embedded as images in generated presentations.

        The function creates a temporary .mmd file, calls mmdc to convert it, and returns
        the path to the output PNG. Temporary files are cleaned up after conversion.
        
        Enforces vertical (top-to-bottom) layout for flowcharts and high-quality output
        by adding rankdir directive and using 2x scaling.

    Features:
        - Supports all Mermaid diagram types (flowchart, sequence, class, state, etc.)
        - Automatic temporary file handling
        - Error handling for missing mmdc binary or conversion failures
        - Vertical layout for flowcharts (rankdir: TB)
        - High-quality output (2x scale)
        - Returns None gracefully if mmdc is not installed
        - Validates PNG file integrity before returning path
    """
    temp_mmd_path = None
    
    try:
        # Ensure vertical (top-to-bottom) layout for flowcharts
        # Replace horizontal flow (LR/RL) with vertical flow (TD/BT)
        mermaid_code_modified = mermaid_code
        
        # Replace LR (left-right) with TD (top-down/vertical)
        mermaid_code_modified = mermaid_code_modified.replace('flowchart LR', 'flowchart TD')
        mermaid_code_modified = mermaid_code_modified.replace('graph LR', 'graph TD')
        
        # Replace RL (right-left) with TD (top-down/vertical)
        mermaid_code_modified = mermaid_code_modified.replace('flowchart RL', 'flowchart TD')
        mermaid_code_modified = mermaid_code_modified.replace('graph RL', 'graph TD')
        
        # Add Mermaid configuration for proper theming and visibility
        # This ensures text is visible with proper colors and contrast
        # Reduced padding for compact output that fits on slides
        mermaid_config = """%%{init: {
  'theme': 'default',
  'primaryColor': '#e8f4f8',
  'primaryTextColor': '#000000',
  'primaryBorderColor': '#4166f5',
  'lineColor': '#4166f5',
  'secondBgColor': '#f0f5ff',
  'tertiaryColor': '#ffffff',
  'tertiaryTextColor': '#000000',
  'fontSize': '14px',
  'fontFamily': 'arial',
  'flowchart': {
    'useMaxWidth': true,
    'padding': 5,
    'nodeSpacing': 30,
    'rankSpacing': 30,
    'htmlLabels': true
  }
}}%%
"""
        
        # Prepend configuration before the diagram code
        if not mermaid_code_modified.strip().startswith('%%{init'):
            mermaid_code_modified = mermaid_config + '\n' + mermaid_code_modified
        
        # Create temporary .mmd file for mermaid code
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False, encoding='utf-8') as temp_mmd:
            temp_mmd.write(mermaid_code_modified)
            temp_mmd.flush()  # Ensure file is flushed to disk
            temp_mmd_path = temp_mmd.name


        # Convert Path object to string for consistency
        output_path_str = str(output_path)
        
        # Ensure output directory exists
        Path(output_path_str).parent.mkdir(parents=True, exist_ok=True)
        
        mmdc_bin = _resolve_mmdc_binary()
        if not mmdc_bin:
            print("WARNING: mmdc (mermaid-cli) not found. Install with: npm install -g @mermaid-js/mermaid-cli")
            print("  Also ensure your npm global bin directory is in PATH.")
            return None

        cmd_list = [
            mmdc_bin,
            '-i', temp_mmd_path,
            '-o', output_path_str,
            '--scale', '1'  # 1x scale to reduce output size on slides
        ]
        
        # Run mmdc subprocess WITHOUT shell=True to avoid Windows path issues
        # Use shell=False with proper list of arguments
        result = subprocess.run(
            cmd_list,
            check=False,  # Don't raise exception - we'll check result ourselves
            timeout=timeout,
            capture_output=True,
            text=True,
            shell=False  # CRITICAL: shell=False with list of args for proper Windows handling
        )
        
        # Check subprocess return code
        if result.returncode != 0:
            print(f"WARNING: Mermaid conversion failed with exit code {result.returncode}")
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}")
            return None
        
        # Validate PNG file was created and has content
        output_path_obj = Path(output_path_str)
        
        if not output_path_obj.exists():
            print(f"WARNING: Mermaid conversion didn't create output file: {output_path_str}")
            return None
        
        # Check file size - valid PNG should be at least a few KB
        file_size = output_path_obj.stat().st_size
        if file_size < 1000:
            print(f"WARNING: Generated PNG file is too small ({file_size} bytes) - likely corrupted: {output_path_str}")
            return None
        
        # Validate PNG header (first 8 bytes should be PNG magic number)
        try:
            with open(output_path_str, 'rb') as f:
                png_header = f.read(8)
                # PNG magic bytes: 137 80 78 71 13 10 26 10
                if png_header[:4] != b'\x89PNG':
                    print(f"WARNING: Output file is not a valid PNG (bad magic bytes): {output_path_str}")
                    return None
        except Exception as e:
            print(f"WARNING: Failed to validate PNG header: {e}")
            return None
        
        # All validations passed - return the path
        return str(output_path_str)

    except subprocess.TimeoutExpired:
        print(f"WARNING: Mermaid conversion timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"WARNING: Unexpected error during Mermaid conversion: {e}")
        return None
    finally:
        # Clean up temporary mmd file
        if temp_mmd_path and os.path.exists(temp_mmd_path):
            try:
                os.remove(temp_mmd_path)
            except Exception:
                pass  # Ignore cleanup errors
