from common.llm_client import generate_json
from prompts.ambiguity_detector import SYSTEM, TEMPLATE


def detect_ambiguities(title: str, description: str) -> list[dict]:
    prompt = TEMPLATE.format(title=title, description=description)
    result = generate_json(prompt, system=SYSTEM)
    return result.get("questions", [])
