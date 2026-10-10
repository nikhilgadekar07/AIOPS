from common.llm_client import generate_json
from prompts.ambiguity_detector import SYSTEM, TEMPLATE


FALLBACK_QUESTIONS = [
    {
        "question": "What exact business outcome should the feature deliver, and what is the acceptance criterion?",
        "assumed_default": "The feature should behave consistently with the app's current API contract and the requirement should be verifiable through realistic API calls.",
    },
    {
        "question": "What input values are valid, and which values should be rejected?",
        "assumed_default": "Only the known domain-valid values should be accepted; any unsupported value should return a clear validation error.",
    },
    {
        "question": "What does success look like in the repository once the change is implemented?",
        "assumed_default": "The repo should expose the expected route behavior and pass a meaningful validation check without breaking adjacent flows.",
    },
]


def detect_ambiguities(title: str, description: str) -> list[dict]:
    prompt = TEMPLATE.format(title=title, description=description)
    try:
        result = generate_json(prompt, system=SYSTEM)
    except Exception:
        return FALLBACK_QUESTIONS

    questions = result.get("questions") if isinstance(result, dict) else None
    if not isinstance(questions, list) or not questions:
        return FALLBACK_QUESTIONS
    return questions
