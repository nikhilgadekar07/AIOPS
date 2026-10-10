from common.llm_client import generate_json
from prompts.ambiguity_detector import SYSTEM, TEMPLATE


def _fallback_questions(description: str) -> list[dict[str, str]]:
    text = description.lower()
    if any(word in text for word in ("school", "academy", "college", "university", "education")):
        return [
            {"question": "Which students and families should this school website speak to?", "assumed_default": "Prospective and current students and their families; avoid inventing specific grades or programs."},
            {"question": "Which school information should be easiest to find?", "assumed_default": "Academics, admissions, student life, and contact details."},
            {"question": "What campus imagery or visual style should the page use?", "assumed_default": "A welcoming campus, learning spaces, and student-life imagery from openly licensed sources, with creator and license credits."},
        ]
    if any(word in text for word in ("website", "web site", "webpage", "landing page")):
        return [
            {"question": "Who is the main audience for this website?", "assumed_default": "The people most likely to use or choose the requested organization; do not invent specific customer claims."},
            {"question": "Which pages or sections are essential for this audience?", "assumed_default": "A clear introduction, the requested offerings, an about section, and a contact action."},
            {"question": "What visual style or image subjects should the website use?", "assumed_default": "A polished, accessible style with requirement-relevant openly licensed images and visible attribution."},
        ]
    if any(word in text for word in ("salon", "barber", "hair")):
        return [
            {"question": "Who is the salon's target clientele?", "assumed_default": "Local clients looking for the services named in the request."},
            {"question": "Which services and booking details should be featured?", "assumed_default": "The requested services, opening hours, location, and a clear appointment action."},
            {"question": "What imagery should set the salon's mood?", "assumed_default": "Interiors, tools, and hairstyle details from openly licensed sources with attribution."},
        ]
    if any(word in text for word in ("restaurant", "cafe", "coffee", "bakery")):
        return [
            {"question": "What kind of guests is this restaurant experience for?", "assumed_default": "People looking for the cuisine or dining experience described in the request."},
            {"question": "Which menu, location, and reservation details should be prominent?", "assumed_default": "A sample menu clearly labeled as editable, location and hours, and a reservation/contact action."},
            {"question": "What food or dining imagery should be featured?", "assumed_default": "Cuisine-relevant food and venue imagery from openly licensed sources with attribution."},
        ]
    return [
        {"question": "Who will use the requested result, and what should they accomplish first?", "assumed_default": "Prioritize the audience and primary outcome explicitly named in the request."},
        {"question": "Which details or capabilities must be included in the first version?", "assumed_default": "Include the requested capabilities and avoid adding unsupported requirements."},
        {"question": "Are there constraints or visual preferences the implementation should respect?", "assumed_default": "Use accessible, responsive defaults and requirement-relevant openly licensed imagery when visuals are needed."},
    ]


def detect_ambiguities(title: str, description: str) -> list[dict]:
    prompt = TEMPLATE.format(title=title, description=description)
    try:
        result = generate_json(prompt, system=SYSTEM)
    except Exception:
        return _fallback_questions(description)

    questions = result.get("questions") if isinstance(result, dict) else None
    if not isinstance(questions, list) or not questions:
        return _fallback_questions(description)
    normalized = [
        {"question": item["question"].strip(), "assumed_default": item.get("assumed_default", "").strip()}
        for item in questions
        if isinstance(item, dict) and isinstance(item.get("question"), str) and item["question"].strip()
    ]
    return normalized[:3] or _fallback_questions(description)
