You are an expert presentation designer.

Create a structured JSON slide plan for the topic below.

Topic: {topic}

Rules:
- Generate exactly {num_slides} slides total. Do not generate more or fewer slides.
- The first slide must be a title slide with type `title`.
- Slide types can be: title, content, diagram, code, chart.
- Each slide can include: title, subtitle, icon, bullets, diagram, diagram_bullets, code, chart, speaker_notes, image_query.
- Use 6–8 bullets for content slides.
- Use emojis as icons in titles when appropriate.
- For each slide, set "image_query" to 2-4 CONCRETE, SPECIFIC English keywords directly related to the slide content (avoid abstract concepts like "communication" or "importance"). Use tangible nouns and descriptors. For topic "{topic}": use specific objects, locations, or actions (e.g., for communication topic: "people talking conversation", "office meeting teamwork", NOT just "communication daily life"). These will be searched in stock photo APIs.
- Use Mermaid diagrams SELECTIVELY for processes, workflows, architectures, relationships, sequences, or systems only when the diagram adds NEW information or a genuinely clearer structure than bullets alone.
- When the topic contains meaningful structure such as processes, architectures, ecosystems/tooling relationships, or comparisons, include 1-3 context-aware diagram slides across the deck.
- Never create a follow-up `Flow`, `Workflow`, `Process`, or `Diagram` slide that simply restates bullet points already covered on an earlier slide.
- If the content is already fully explained by bullets on another slide, leave "diagram" empty and keep the slide as bullets instead of creating a duplicate flowchart.
- Across the full deck, use Mermaid diagrams on at most 3 slides total.
- Diagram node labels must be concrete and topic-specific. Use actual entities from the slide such as tool names, frameworks, package managers, services, APIs, user groups, components, or explicit domain steps.
- Never use generic placeholder node labels such as `Retrieve Context`, `Process Information`, `Generate Output`, `Deliver Result`, `Input`, `Output`, `Step 1`, `Step 2`, `Start`, or `End`.
- For ecosystem/tooling slides, diagrams must mention real tools or ecosystem components. If you cannot name concrete items such as package managers, libraries, IDEs, build tools, runtimes, or deployment targets, leave "diagram" empty and use bullets.
- Do NOT create a diagram for simple overview, summary, strengths, benefits, or feature-list slides unless there is a real process, sequence, architecture, or relationship to visualize. Avoid generic placeholder slides such as `Overview ... Flow`.
- For comparison slides, if you create a diagram, derive the node categories and labels directly from the slide title and bullet content. Do not invent generic buckets or placeholder labels. If the slide content is not specific enough to produce a meaningful, topic-relevant diagram, leave "diagram" empty and use bullets instead.
- Every diagram slide must stand on its own with distinct content. Do not duplicate the same facts in both a normal content slide and a separate flowchart slide unless the flowchart introduces additional steps, dependencies, or structure not stated elsewhere.
- The "diagram" field must contain ONLY valid Mermaid syntax (first line must start with: graph, flowchart, sequenceDiagram, classDiagram, stateDiagram, erDiagram, gantt, pie, journey, gitGraph, mindmap, timeline). Generate diagrams with FULL, DESCRIPTIVE text labels in SQUARE BRACKETS for EVERY node. REQUIRED FORMAT: `NodeId[Full Label Text] --> NextNode[Next Label Text]`. NEVER use bare node IDs without brackets. Each node MUST have descriptive text in brackets (e.g., `OilPrice[Oil Price Increase] --> TransportCosts[Higher Transport Costs]`, NOT just `OilPrice --> TransportCosts`). If you cannot generate valid meaningful Mermaid with full descriptions in brackets for every node, leave "diagram" as an empty string and add bullets instead.
- For every slide with a non-empty "diagram", ALSO include "diagram_bullets": 3-5 concise bullet points that explain the same diagram in plain English. These are backup bullets that are shown only if diagram rendering fails.
- If a slide does not need a diagram, set "diagram_bullets" to an empty array.
- "diagram_bullets" must be tightly related to the Mermaid diagram and should summarize the steps, relationships, or comparisons shown in the diagram.
- For charts: ALWAYS include a "description" field explaining the unit or meaning (e.g., "Visitor Count (thousands)", "Growth Rate (%)", "Annual Revenue (USD)"). Include specific, meaningful numbers, not placeholders.
- Keep JSON valid and return JSON only.

Schema:

{
  "title": "",
  "slides": [
    {
      "type": "title",
      "title": "",
      "subtitle": "",
      "icon": "",
      "image_query": "",
      "bullets": [],
      "diagram": "",
      "diagram_bullets": [],
      "code": {"language":"", "content":""},
      "chart": {"type":"", "description": "", "labels":[], "values":[]},
      "speaker_notes": ""
    }
  ]
}

Chart description field MUST explain what the values represent (e.g., "Visitor Count (in thousands)", "Annual Revenue (USD)", "Growth Rate (%)").
Diagram notes: Generated diagrams are now rendered as PNG images in your presentation, making them more visually compelling and easier to understand.
