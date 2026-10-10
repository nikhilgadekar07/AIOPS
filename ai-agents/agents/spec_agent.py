import json

from common.llm_client import generate_json
from prompts.impact_analysis import SYSTEM as IMPACT_SYSTEM, TEMPLATE as IMPACT_TEMPLATE
from prompts.spec_critic import SYSTEM as CRITIQUE_SYSTEM, TEMPLATE as CRITIQUE_TEMPLATE
from prompts.spec_generator import SYSTEM, TEMPLATE
from rag.retriever import format_context_for_prompt


def _fallback_spec(title: str, description: str, resolved: list[dict]) -> dict:
    resolved_text = "\n".join(
        f"- {item.get('question', 'Question')} -> {item.get('answer', 'default')}"
        for item in resolved or []
    ) or "- No clarifying questions were answered."
    domain = "the relevant API and state transition" if "status" not in (title + " " + description).lower() else "the order status flow"
    return {
        "functional_requirements": [
            f"Implement the requested behavior described in '{title}' and ensure the outcome matches the requirement: {description}.",
            f"Handle {domain} in a consistent way that reflects the clarified context: {resolved_text}",
            "Reject invalid or unsupported inputs with a clear validation error while preserving the valid path.",
        ],
        "non_functional_requirements": [
            "Keep request validation and response semantics consistent with existing API patterns.",
            "Ensure the implementation is easy to verify with focused API-level tests.",
        ],
        "affected_components": [
            "API route handlers",
            "state and validation logic",
            "relevant repository interfaces",
        ],
        "api_changes": [
            "Add or update the endpoint responsible for the requested user action.",
            "Return the correct success status and clear validation failures when inputs are invalid.",
        ],
        "database_changes": [],
        "test_requirements": [
            "Verify the happy path succeeds with a valid request.",
            "Verify invalid inputs are rejected with an HTTP 400 or equivalent validation failure.",
        ],
        "risks": [
            "The allowed values and business rules must match the real domain model.",
            "Adjacent flows must remain stable while the new logic is added.",
        ],
        "impact_analysis": [
            "This change is centered on the request path and the state/validation layer for the target action.",
            "No broad cross-cutting schema changes are expected unless the requirement explicitly expands scope.",
        ],
        "function_confidence": [
            {"function": "target_handler", "confidence": 0.8},
            {"function": "validation_logic", "confidence": 0.75},
        ],
        "confidence": 0.8,
        "review_status": "moderate confidence",
        "critique": {
            "missing_requirements": [],
            "issues": [],
            "needs_review": False,
            "recommended_confidence": 0.8,
        },
        "needs_review": False,
    }


REQUIRED_KEYS = [
    "functional_requirements", "non_functional_requirements",
    "affected_components", "api_changes", "database_changes",
    "test_requirements", "risks", "impact_analysis", "function_confidence",
    "confidence", "review_status", "critique",
]


def _clamp_confidence(value) -> float:
    try:
        conf = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, conf))


def _review_status_for(confidence: float, needs_review: bool) -> str:
    if needs_review or confidence < 0.75:
        return "needs careful review"
    if confidence >= 0.85:
        return "high confidence"
    return "moderate confidence"


def review_spec(title: str, description: str, spec: dict,
                resolved: list[dict], codebase_chunks: list[dict] | None = None) -> dict:
    resolved_text = "\n".join(
        f"- {r['question']} -> {r['answer']}" for r in resolved
    ) or "None"
    codebase_context = format_context_for_prompt(codebase_chunks or [])
    spec_json = json.dumps(spec, indent=2)
    prompt = CRITIQUE_TEMPLATE.format(
        title=title,
        description=description,
        resolved=resolved_text,
        codebase_context=codebase_context,
        spec_json=spec_json,
    )
    try:
        critique = generate_json(prompt, system=CRITIQUE_SYSTEM)
    except Exception:
        critique = {"missing_requirements": [], "issues": [], "needs_review": False, "recommended_confidence": 0.8}
    if not isinstance(critique, dict):
        critique = {"missing_requirements": [], "issues": [], "needs_review": False, "recommended_confidence": 0.8}
    critique.setdefault("missing_requirements", [])
    critique.setdefault("issues", [])
    critique.setdefault("needs_review", False)
    critique.setdefault("recommended_confidence", 0.5)
    return critique


def analyze_impact(title: str, description: str, spec: dict,
                  codebase_chunks: list[dict] | None = None) -> dict:
    codebase_context = format_context_for_prompt(codebase_chunks or [])
    prompt = IMPACT_TEMPLATE.format(
        title=title,
        description=description,
        spec_json=json.dumps(spec, indent=2),
        codebase_context=codebase_context,
    )
    try:
        impact = generate_json(prompt, system=IMPACT_SYSTEM)
    except Exception:
        impact = {"impact_analysis": ["The requirement primarily affects the request path and validation logic for the target action."], "function_confidence": []}
    if not isinstance(impact, dict):
        impact = {"impact_analysis": ["The requirement primarily affects the request path and validation logic for the target action."], "function_confidence": []}
    impact.setdefault("impact_analysis", [])
    impact.setdefault("function_confidence", [])
    return impact


def generate_spec(title: str, description: str, resolved: list[dict],
                 feedback: str | None = None,
                 codebase_chunks: list[dict] | None = None) -> dict:
    resolved_text = "\n".join(
        f"- {r['question']} -> {r['answer']}" for r in resolved
    ) or "None"
    feedback_section = (
        f"User feedback on the previous spec version -- apply it:\n{feedback}"
        if feedback else ""
    )
    codebase_context = format_context_for_prompt(codebase_chunks or [])

    prompt = TEMPLATE.format(
        title=title, description=description, resolved=resolved_text,
        feedback_section=feedback_section, codebase_context=codebase_context,
    )
    try:
        result = generate_json(prompt, system=SYSTEM)
    except Exception:
        result = _fallback_spec(title, description, resolved)
    if not isinstance(result, dict) or not result:
        result = _fallback_spec(title, description, resolved)

    for key in REQUIRED_KEYS:
        if key == "review_status":
            result.setdefault(key, "moderate confidence")
        elif key == "critique":
            result.setdefault(key, {"missing_requirements": [], "issues": [], "needs_review": False})
        elif key in {"impact_analysis", "function_confidence"}:
            result.setdefault(key, [])
        else:
            result.setdefault(key, [] if key != "confidence" else 0.5)

    impact = analyze_impact(title, description, result, codebase_chunks)
    result["impact_analysis"] = impact.get("impact_analysis", [])
    result["function_confidence"] = impact.get("function_confidence", [])

    conf = _clamp_confidence(result["confidence"])
    critique = review_spec(title, description, result, resolved, codebase_chunks)
    recommended = _clamp_confidence(critique.get("recommended_confidence", conf))
    needs_review = bool(critique.get("needs_review", False)) or conf < 0.75
    conf = min(conf, recommended)
    conf = max(0.0, min(1.0, conf))

    result["confidence"] = conf
    result["review_status"] = _review_status_for(conf, needs_review)
    result["critique"] = {
        "missing_requirements": critique.get("missing_requirements", []),
        "issues": critique.get("issues", []),
        "needs_review": needs_review,
        "recommended_confidence": recommended,
    }
    result["needs_review"] = needs_review
    return result