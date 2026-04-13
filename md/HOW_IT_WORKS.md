---
marp: true
paginate: true
---

# How Does the Automated PPT Generator Work?

## Introduction

Imagine you want to create a professional PowerPoint presentation on any topic—instantly. This tool does exactly that: you give it a topic, and it builds a complete, visually appealing presentation for you, using artificial intelligence and smart automation.

Let's walk through how it works, step by step.

---

## Step 0 — You Choose a Mode

When you run the tool, it first asks you to choose between two workflows:

| Choice | Mode | Description |
|--------|------|-------------|
| `1` | **Topic to PPT** | Generate a brand-new presentation from scratch by entering a topic |
| `2` | **Markdown to PPT** | Convert an existing Marp-formatted `.md` file directly into a PowerPoint file, skipping all AI generation |

---

## Step 1 — You Provide a Topic *(Topic to PPT only)*

If you chose mode 1, the tool asks you to type a topic in plain English — for example, *"What is CSS"* or *"How AI is Changing Our Lives."* No technical knowledge is needed.

---

## Step 2 — You Specify the Number of Slides *(Topic to PPT only)*

After providing the topic, the tool asks how many slides you want in your presentation. You can enter any number greater than 0, or press Enter to use the default of **16 slides**. This gives you control over presentation length—whether you want a quick 5-slide overview or a comprehensive 30-slide deep dive.

---

## Step 3 — API Status Check

Before doing anything else, the tool reports which image APIs are configured (Unsplash, Pexels, or neither), so you know upfront what image sources will be used or whether it will fall back to a placeholder.

---

## Step 4 — The Tool Plans the Slides with AI

Behind the scenes, the tool:

1. Loads a prompt template from the local file `md/prompt.md`
2. Substitutes your topic into the template
3. Sends it to **GPT-5.4-mini** (OpenAI) at a low temperature (`0.2`) for consistent, structured output

> The tool always checks that the first slide is a **title slide**, and inserts a default one if the AI omitted it.

---

<!-- _style: "section { font-size: 16px; }" -->

## Step 4 (cont.) — What Each Slide Contains

The AI returns a **JSON slide plan** — a list of slides, each with:

| Field | Description |
|-------|-------------|
| `type` | Slide category: title, content, etc. |
| `title` / `subtitle` | Slide heading and subheading |
| `bullets` | Key bullet points |
| `image_query` | Search term for fetching a photo |
| `diagram` | Optional Mermaid diagram source code |
| `code` | Optional code block (language + content) |
| `chart` | Optional chart data (type, labels, values) |
| `speaker_notes` | Notes for the presenter view |

---

## Step 5 — It Searches for and Downloads Images in Parallel

For each slide, the tool generates a targeted image search query and tries to download a relevant landscape photo using a **priority fallback chain**:

```
Unsplash  →  Pexels  →  picsum.photos (free placeholder)
```

- **Unsplash** is tried first if an API key is configured
- **Pexels** is tried next if an API key is configured
- **picsum.photos** is used as a last resort when both APIs are unavailable or return no results

> All image downloads run **in parallel** using Python's `ThreadPoolExecutor` to keep generation fast.

---

## Step 6 — It Renders Mermaid Diagrams

If any slide includes a Mermaid diagram (e.g., a flowchart or sequence diagram), the tool:

1. Enforces a **vertical (top-to-bottom) layout** for readability — replacing `LR`/`RL` with `TD`
2. Applies a **consistent visual theme** with readable colors and contrast
3. Calls the **Mermaid CLI (`mmdc`)** to render the diagram as a PNG image
4. Embeds that PNG directly into the slide

> If `mmdc` is not installed or the diagram fails to render, the slide falls back gracefully to bullet-point text extracted from the diagram's node labels.

---

<!-- _style: "section { font-size: 16px; }" -->

## Step 7 — It Assembles Everything into Marp Markdown

The tool combines all content into a single **Marp-formatted Markdown file**:

| Element | How It's Handled |
|---------|-----------------|
| Title slides | Dark background, large left-side image, prominent typography |
| Content slides | Image on the right at 35% width for a balanced layout |
| Mermaid diagrams | Rendered as PNG and embedded as images |
| Code blocks | Syntax-highlighted fenced blocks |
| Speaker notes | Embedded as HTML comments for presenter view |
| Closing slide | Fixed "Thank You" slide always appended at the end |

The finished Markdown file is saved to disk, named after your topic.

---

## Step 8 — It Converts the Markdown to PowerPoint

The tool invokes the **Marp CLI** as a subprocess, passing the saved `.md` file with the `--pptx` flag:

- On **Windows**, it directly calls `node marp-cli.js` to avoid issues with `.CMD` wrapper scripts
- A **180-second timeout** guards against the process hanging
- The resulting `.pptx` file is saved alongside the `.md` file

---

<!-- _style: "section { font-size: 16px; }" -->

## Step 9 — You Get the Finished Presentation

The tool prints the path to the generated `.pptx` file along with timing information for each stage:

```
[2.3s] Slide plan generated (10 slides)
[8.1s] Markdown rendered (includes image downloads)
[0.1s] Markdown saved: PPT/what_is_css.md
[12.4s] PPTX export finished
[22.9s] Total
```

You can open the file in Microsoft PowerPoint immediately, present it, or edit it further.

---

<!-- _style: "section { font-size: 14px; }" -->

## Technical Reference — Module Breakdown (1/2)

| Step | Module | What It Does |
|------|--------|--------------|
| Mode selection | `main.py` | Prompts user for mode 1 or 2; routes to the correct workflow |
| API status check | `main.py` → `marp_core/config.py` | Reports Unsplash/Pexels key availability before generation |
| Slide planning | `marp_core/slide/generator.py` | Fills `prompt.md` template, calls GPT-5.4-mini, parses JSON plan |
| Image query generation | `marp_core/image/query_generator.py` | Produces optimal search queries per slide |

---

<!-- _style: "section { font-size: 14px; }" -->

## Technical Reference — Module Breakdown (2/2)

| Step | Module | What It Does |
|------|--------|--------------|
| Image fetching | `marp_core/image/fetcher.py` | Downloads images from Unsplash → Pexels → picsum in parallel |
| Diagram rendering | `marp_core/utils/mermaid.py` | Calls `mmdc` to convert Mermaid source to PNG |
| Markdown rendering | `marp_core/slide/renderer.py` | Assembles full Marp markdown with CSS, images, diagrams, and speaker notes |
| File save | `marp_core/io/file.py` | Persists the `.md` file to disk |
| PPTX export | `marp_core/export/marp.py` | Invokes Marp CLI subprocess to produce the final `.pptx` |

---

<!-- _style: "section { font-size: 15px; }" -->

## Requirements

| Requirement | Purpose |
|-------------|---------|
| OpenAI API key | Slide plan generation via GPT-5.4-mini |
| Unsplash API key *(optional)* | Primary image source |
| Pexels API key *(optional)* | Secondary image source |
| Marp CLI (`npm install -g @marp-team/marp-cli`) | PPTX export |
| Mermaid CLI (`npm install -g @mermaid-js/mermaid-cli`) | Diagram rendering |

---

## Why Is This Useful?

- **Saves Time** — Go from idea to finished deck in minutes, no manual slide building required
- **Two Workflows** — Generate fresh content with AI, or convert an existing Markdown file you've already written
- **Resilient Image Sourcing** — Three-level fallback means slides always have visuals, even without API keys
- **Diagram Support** — Mermaid diagrams are rendered automatically as images, not just pasted as code
- **Consistent Quality** — Every slide follows a fixed visual style and always ends with a closing slide

---

## Conclusion

This tool brings together OpenAI's language models, parallel image fetching from Unsplash and Pexels, Mermaid diagram rendering, and the Marp CLI into a single automated pipeline.

**You type a topic. It delivers a polished, presenter-ready PowerPoint file.**
