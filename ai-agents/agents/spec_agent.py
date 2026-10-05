from common.llm_client import generate_json
from prompts.spec_generator import SYSTEM, TEMPLATE


def generate_spec(title: str, description: str, resolved: list[dict]) -> dict:
    resolved_text = "\n".join(
        f"- {r['question']} -> {r['answer']}" for r in resolved
    )
    prompt = TEMPLATE.format(title=title, description=description, resolved=resolved_text)
    return generate_json(prompt, system=SYSTEM)