You are an expert presentation designer.

Create a structured JSON slide plan for the topic below.

Topic: {topic}

Rules:
- Generate 15-16 slides total (maximum capacity for a comprehensive presentation).
- The first slide must be a title slide with type `title`.
- Slide types can be: title, content, diagram, code, chart.
- Each slide can include: title, subtitle, icon, bullets, diagram, code, chart, speaker_notes, image_query.
- Use 3–5 bullets for content slides.
- Use emojis as icons in titles when appropriate.
- For each slide, set "image_query" to 2-4 CONCRETE, SPECIFIC English keywords directly related to the slide content (avoid abstract concepts like "communication" or "importance"). Use tangible nouns and descriptors. For topic "{topic}": use specific objects, locations, or actions (e.g., for communication topic: "people talking conversation", "office meeting teamwork", NOT just "communication daily life"). These will be searched in stock photo APIs.
- **PRIORITIZE FLOWCHARTS AND DIAGRAMS**: Use Mermaid diagrams for ANY content about processes, workflows, architectures, relationships, sequences, or systems. These will be rendered as high-quality PNG images in the presentation. Flowcharts are excellent for explaining HOW things work.
- The "diagram" field must contain ONLY valid Mermaid syntax (first line must start with: graph, flowchart, sequenceDiagram, classDiagram, stateDiagram, erDiagram, gantt, pie, journey, gitGraph, mindmap, timeline). Generate diagrams with FULL, DESCRIPTIVE text labels in SQUARE BRACKETS for EVERY node. REQUIRED FORMAT: `NodeId[Full Label Text] --> NextNode[Next Label Text]`. NEVER use bare node IDs without brackets. Each node MUST have descriptive text in brackets (e.g., `OilPrice[Oil Price Increase] --> TransportCosts[Higher Transport Costs]`, NOT just `OilPrice --> TransportCosts`). If you cannot generate valid meaningful Mermaid with full descriptions in brackets for every node, leave "diagram" as an empty string and add bullets instead.
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
      "code": {"language":"", "content":""},
      "chart": {"type":"", "description": "", "labels":[], "values":[]},
      "speaker_notes": ""
    }
  ]
}

Chart description field MUST explain what the values represent (e.g., "Visitor Count (in thousands)", "Annual Revenue (USD)", "Growth Rate (%)").
Diagram notes: Generated diagrams are now rendered as PNG images in your presentation, making them more visually compelling and easier to understand.