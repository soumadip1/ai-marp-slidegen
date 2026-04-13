"""
Slide plan generation using GPT-5.4-mini.

Generates complete slide plans from presentation topics.
"""
import json
from importlib import resources
from openai import OpenAI
from ..config import OPENAI_API_KEY
from ..utils.text import sanitize_text
from .diagram_optimizer import optimize_diagram_placement

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def generate_slide_plan(topic, num_slides=16):
    """
    Generate a complete slide plan for a presentation topic using GPT-5.4-mini.
    
    Args:
        topic (str): The presentation topic
        num_slides (int): The number of slides to generate (default 16)
    
    Returns:
        dict: Slide plan with structure: {title, slides: [{type, title, subtitle, icon, 
              image_query, bullets, diagram, code, chart, speaker_notes}, ...]}
    
    Description:
        Loads the prompt template from the bundled marp_core/templates/prompt.md file.
        Sends it to GPT-5.4-mini with the topic and num_slides substituted.
        Parses JSON response and ensures first slide is a title slide.
        Returns structured slide plan ready for rendering.
    """
    # Load bundled prompt template using importlib.resources (works when installed as a package)
    try:
        prompt_template = resources.files("marp_core.templates").joinpath("prompt.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        print("ERROR: bundled prompt.md not found inside the marp_core package.")
        exit(1)
    
    # Substitute {topic} and {num_slides} placeholders in the prompt using replace (safer than format())
    # format() would fail because JSON schema contains {} braces
    prompt = prompt_template.replace("{topic}", topic).replace("{num_slides}", str(num_slides))

    # Call GPT-4o-mini with prompt to generate slide plan
    # Temperature 0.2 keeps outputs consistent while still being creative
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}]
    )

    # Parse JSON response from GPT
    plan = json.loads(response.choices[0].message.content)

    # Ensure first slide is a title slide (safety check in case GPT fails)
    if not plan.get("slides") or plan["slides"][0].get("type") != "title":
        # Insert default title slide at the beginning
        plan.setdefault("slides", []).insert(0, {
            "type": "title",
            "title": topic,
            "subtitle": f"A concise overview of {topic}",
            "icon": "🌍",
            "image_query": topic,
            "bullets": [],
            "diagram": "",
            "code": {"language": "", "content": ""},
            "chart": {"type": "", "labels": [], "values": []},
            "speaker_notes": "Title slide introducing the topic and setting visual tone."
        })

    # Optimize diagram placement: defer diagrams from overcrowded slides to next slide
    print("Optimizing diagram placement...")
    plan = optimize_diagram_placement(plan)

    return plan
