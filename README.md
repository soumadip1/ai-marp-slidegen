# Marp Presentation Generator

Automated "topic to PowerPoint" pipeline powered by OpenAI GPT and the Marp CLI.  
Give it a topic and it returns a fully styled `.pptx` file — with downloaded stock images, Mermaid diagrams, and speaker notes.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Structure Diagram](#structure-diagram)
- [Module Reference](#module-reference)
- [Building a Distributable Package](#building-a-distributable-package)

---

## How It Works

1. You provide a topic (or an existing Marp `.md` file).
2. GPT-5.4-mini generates a structured JSON slide plan with titles, bullets, image queries, and diagram code.
3. Stock images are downloaded in parallel from Unsplash → Pexels → picsum (automatic fallback chain).
4. Mermaid diagrams are rendered to PNG via `mmdc`.
5. A Marp-flavoured Markdown file is assembled and saved.
6. Marp CLI converts the Markdown to a fully styled `.pptx` file.
7. [Detailed "How It Works" Guide](md/HOW_IT_WORKS.md)
---

## Prerequisites

All tools below must be installed before running the generator.

### 1. Python 3.10 or later

Download from [python.org](https://www.python.org/downloads/).  
Verify:

```bash
python --version
```

### 2. Node.js (LTS recommended)

Required by both Marp CLI and Mermaid CLI.  
Download from [nodejs.org](https://nodejs.org/).  
Verify:

```bash
node --version
npm --version
```

### 3. Marp CLI

Converts Marp Markdown to `.pptx`.

```bash
npm install -g @marp-team/marp-cli
```

Verify:

```bash
marp --version
```

### 4. Mermaid CLI (`mmdc`)

Renders Mermaid diagram code blocks to PNG images.

```bash
npm install -g @mermaid-js/mermaid-cli
```

Verify:

```bash
mmdc --version
```

### 5. API Keys

| Key | Required | Used For |
|-----|----------|----------|
| `OPENAI_API_KEY` | **Yes** | Slide plan generation via GPT-5.4-mini |
| `UNSPLASH_API_KEY` | Optional | Stock image downloads (tried first) |
| `PEXELS_API_KEY` | Optional | Stock image downloads (fallback) |

If neither Unsplash nor Pexels keys are provided, images fall back to [picsum.photos](https://picsum.photos) placeholders automatically.

---

## Installation

### Option A — Run from source (recommended for development)

```bash
# 1. Clone the repository
git clone <repo-url>
cd marp-generator

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

# 3. Install Python dependencies
pip install -e .
```

### Option B — Install as a Python package (pip)

```bash
# 1. Go to the project directory
cd C:\Users\souma\OneDrive\Code\marp-generator

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
# Windows (cmd.exe):   
.venv\Scripts\activate.bat

# Windows (PowerShell): 
.venv\Scripts\Activate.ps1

# macOS / Linux:       
source .venv/bin/activate

# 4. Install the built wheel
python -m pip install .\dist\marp_generator-2.0.0-py3-none-any.whl

# Alternative: editable install from a local checkout
python -m pip install -e path/to/marp-generator
```

After installation, the `marp-gen` command is available in the Python environment where you installed the package.

To use `marp-gen` directly, activate that environment first.

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- Windows (cmd.exe): `.venv\Scripts\activate.bat`
- macOS / Linux: `source .venv/bin/activate`

---

## Configuration

Create a `.env` file in the directory where you will run the tool. The CLI reads `.env` from the current working directory, not from the installed package location:

```env
OPENAI_API_KEY=sk-...

# Optional — improves image quality
UNSPLASH_API_KEY=your_unsplash_key
PEXELS_API_KEY=your_pexels_key
```

`OPENAI_API_KEY` is required for `Topic to PPT` mode. `Markdown file to PPT` can still run without it.

Output folders (`PPT/` and `assets/`) are created automatically inside your current working directory.

Example:

```bash
mkdir my-decks
cd my-decks

# Put your .env here, then run:
marp-gen
```

Typical workflow after installing into a virtual environment:

```bash
cd marp-generator

# activate the environment where marp-generator was installed
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows cmd.exe:   .venv\Scripts\activate.bat
# macOS / Linux:     source .venv/bin/activate

cd ../my-decks
marp-gen
```

At runtime, the CLI creates `PPT/`, `assets/`, and reads `.env` in the current working directory where you launch `marp-gen`. The `build/`, `dist/`, and `*.egg-info/` paths are generated packaging artifacts rather than source files.

---

## Usage

### Interactive CLI

```bash
# From source
python main.py

# After installing into an activated environment
marp-gen
```

If `marp-gen` is not recognized, the package is usually installed into a different Python environment than the one your shell is using. Activate the correct environment and try again.

You will be prompted to choose a mode:

```
Choose conversion mode:
1. Topic to PPT
2. Markdown file to PPT
Enter 1 or 2:
```

#### Mode 1 — Topic to PPT

Enter any topic and the full pipeline runs automatically:

```
Enter topic: Introduction to Kubernetes
```

Output: `PPT/<topic>.pptx` and `PPT/<topic>.md`

#### Mode 2 — Markdown file to PPT

Provide the path to an existing Marp-formatted `.md` file:

```
Enter full path to markdown file: C:\Users\you\docs\my_slides.md
```

Output: `.pptx` file in the same directory as the input file.

---

## Project Structure

```
marp-generator/
├── main.py                   # CLI entry point
├── pyproject.toml            # Package metadata and dependencies
├── .env                      # API keys (create this yourself — never commit)
├── marp_core/                # Core library package
│   ├── config.py             # API keys, output directories, constants
│   ├── templates/
│   │   └── prompt.md         # GPT prompt template (bundled with package)
│   ├── slide/
│   │   ├── generator.py      # Calls GPT-5.4-mini, returns JSON slide plan
│   │   └── renderer.py       # Assembles final Marp Markdown
│   ├── image/
│   │   ├── fetcher.py        # Downloads images (Unsplash → Pexels → picsum)
│   │   └── query_generator.py# Produces optimised image search queries
│   ├── utils/
│   │   ├── mermaid.py        # Calls mmdc to render diagrams to PNG
│   │   ├── text.py           # Text sanitisation helpers
│   │   └── validators.py     # Input validation utilities
│   ├── export/
│   │   └── marp.py           # Invokes Marp CLI subprocess → .pptx
│   └── io/
│       └── file.py           # Saves Markdown file to disk
├── md/                       # Documentation and slide sources
│   ├── README.md             # This file
│   └── prompt.md             # Source copy of the GPT prompt template
├── PPT/                      # Generated .md and .pptx files (auto-created)
└── assets/                   # Downloaded images (auto-created)
```

---

## Structure Diagram

For a visual version of the runtime project layout, see:

- [Project Structure Diagram](md/project-structure.md)
- [Flow Diagram](md/flow_diagram.md)
- [Technical Architecture](md/technical_architecture.md)
---

## Module Reference

| Module | File | Responsibility |
|--------|------|----------------|
| Entry point | `main.py` | Mode selection, orchestration, timing |
| Configuration | `marp_core/config.py` | Loads `.env`, defines output paths and constants |
| Slide planner | `marp_core/slide/generator.py` | GPT-5.4-mini JSON slide plan generation |
| Slide renderer | `marp_core/slide/renderer.py` | Assembles full Marp Markdown with CSS and images |
| Image queries | `marp_core/image/query_generator.py` | Converts slide context to optimised search terms |
| Image fetcher | `marp_core/image/fetcher.py` | Parallel image downloads with fallback chain |
| Diagram renderer | `marp_core/utils/mermaid.py` | Converts Mermaid source to PNG via `mmdc` |
| File I/O | `marp_core/io/file.py` | Persists Markdown to the current working directory's `PPT/` folder |
| PPTX exporter | `marp_core/export/marp.py` | Invokes Marp CLI to produce final `.pptx` |

---

## Building a Distributable Package

```bash
# Install build tool
pip install build

# Build source distribution and wheel
python -m build

# Output is in dist/
# dist/marp_generator-2.0.0-py3-none-any.whl
# dist/marp_generator-2.0.0.tar.gz
```

Install the wheel on any machine:

```bash
pip install dist/marp_generator-2.0.0-py3-none-any.whl
```

Then run the installed CLI from any folder that contains your `.env` file:

```bash
marp-gen
```

Generated `PPT/` and `assets/` folders will be created in whatever directory you launch the command from.

Generated packaging artifacts such as `build/`, `dist/`, and `*.egg-info/` are local build outputs and should not be committed to git.

> **Note:** Node.js, Marp CLI, and Mermaid CLI must still be installed separately on the target machine — they are external tools and cannot be bundled in a Python wheel.
