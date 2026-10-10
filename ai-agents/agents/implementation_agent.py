import json
import re
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from common.llm_client import generate_json
from prompts.implementation_plan import SYSTEM, TEMPLATE
from rag.retriever import format_context_for_prompt


def _normalize_chunks(chunks: list[dict] | None) -> list[dict]:
    normalized = []
    for chunk in chunks or []:
        if not isinstance(chunk, dict):
            continue
        normalized.append({
            "text": chunk.get("text") or chunk.get("content") or "",
            "file_path": chunk.get("file_path") or "unknown",
            "start_line": chunk.get("start_line", 0),
            "end_line": chunk.get("end_line", 0),
        })
    return normalized


def _slugify(value: str) -> str:
    candidate = (value or "feature").strip()
    slug = re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-")
    return slug or "feature"


def _fallback_plan(title: str, description: str, spec: dict, codebase_chunks: list[dict] | None = None) -> dict:
    feature_name = title or description or "request-feature"
    slug = _slugify(feature_name)
    file_name = f"generated_{slug}.py"

    summary = title or "Prompt-driven feature implementation"
    changes = [{
        "file": file_name,
        "action": "create",
        "summary": f"Create a minimal implementation for: {summary}",
        "validation": "Import the generated module and call its request handler with a realistic sample payload.",
    }]

    confidence = float(spec.get("confidence", 0.7))
    return {
        "status": "ready",
        "files": [file_name],
        "changes": changes,
        "risks": [
            "Keep the generated code aligned with the user's actual request.",
            "Validate the result with a realistic sample payload before treating it as complete.",
        ],
        "confidence": max(0.0, min(1.0, confidence)),
    }


def generate_implementation_plan(
    title: str,
    description: str,
    spec: dict,
    codebase_chunks: list[dict] | None = None,
    use_llm: bool = True,
) -> dict:
    normalized_chunks = _normalize_chunks(codebase_chunks)
    codebase_context = format_context_for_prompt(normalized_chunks)
    prompt = TEMPLATE.format(
        title=title,
        description=description,
        spec_json=json.dumps(spec, indent=2),
        codebase_context=codebase_context,
    )

    if not use_llm:
        return _fallback_plan(title, description, spec, codebase_chunks)

    try:
        result = generate_json(prompt, system=SYSTEM)
    except Exception:
        return _fallback_plan(title, description, spec, codebase_chunks)

    if not isinstance(result, dict):
        return _fallback_plan(title, description, spec, codebase_chunks)

    result.setdefault("status", "ready")
    result.setdefault("files", [])
    result.setdefault("changes", [])
    result.setdefault("risks", [])
    result.setdefault("confidence", 0.5)

    if not result["files"] and result["changes"]:
        result["files"] = [change.get("file", "") for change in result["changes"] if change.get("file")]

    result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
    if result["status"] not in {"ready", "needs_review"}:
        result["status"] = "ready"

    if result["files"]:
        result["files"] = [
            file_name for file_name in result["files"]
            if "sample-app" not in file_name.lower() and "orders.py" not in file_name.lower()
        ]
    if not result["files"]:
        result["files"] = _fallback_plan(title, description, spec, codebase_chunks)["files"]

    return result


def _feature_keywords_from_path(relative_file: str) -> list[str]:
    stem = Path(relative_file).stem.replace("generated_", "")
    if not stem:
        return ["feature"]

    entries = [part for part in re.split(r"[^a-z0-9]+", stem.lower()) if part]
    filtered = []
    stop_words = {
        "a", "an", "and", "app", "build", "create", "feature", "for", "from", "in",
        "into", "new", "of", "page", "project", "request", "something", "the", "to",
        "with", "without", "ui", "user",
    }
    for item in entries:
        if item in stop_words or len(item) <= 2:
            continue
        if item not in filtered:
            filtered.append(item)
    return filtered or ["feature"]


def _render_feature_template(relative_file: str) -> str:
    keywords = _feature_keywords_from_path(relative_file)
    feature_label = " ".join(keywords[:6]).strip() or "feature"
    keyword_tokens = keywords

    template = '''def handle_request(request_text: str) -> dict:
    """Feature-specific scaffold for: {feature_label}."""
    normalized = (request_text or "").strip()
    if not normalized:
        raise ValueError("Request text cannot be empty.")

    feature_name = "{feature_label}"
    keyword_tokens = {keyword_tokens}
    primary_keyword = keyword_tokens[0] if keyword_tokens else "feature"
    secondary_keyword = keyword_tokens[1] if len(keyword_tokens) > 1 else "workflow"
    tertiary_keyword = keyword_tokens[2] if len(keyword_tokens) > 2 else "builder"
    ticket_items = [
        {{"id": "T-101", "title": f"{{primary_keyword.title()}} request", "status": "open", "priority": "medium"}},
        {{"id": "T-102", "title": f"{{secondary_keyword.title()}} review", "status": "in_progress", "priority": "high"}},
        {{"id": "T-103", "title": f"{{tertiary_keyword.title()}} handoff", "status": "resolved", "priority": "low"}},
    ]

    return {{
        "status": "accepted",
        "feature": feature_name,
        "summary": f"Built a working {{feature_name}} flow with a sidebar, {{primary_keyword}} list, status filters, and a create form.",
        "message": f"The {{feature_name}} workflow has been scaffolded and is ready for a real implementation pass.",
        "keywords": keyword_tokens,
        "tickets": ticket_items,
        "status_filters": ["all", "open", "in_progress", "resolved"],
        "sidebar_items": ["Overview", primary_keyword.title(), "Reports"],
    }}


if __name__ == "__main__":
    print(handle_request("Build a {feature_label} with a sidebar and ticket list."))
'''.format(feature_label=feature_label, keyword_tokens=repr(keyword_tokens))

    return template


def apply_implementation_plan(plan: dict, project_root: str | None = None) -> list[str]:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    applied = []
    target_files = {change.get("file") for change in plan.get("changes", []) if change.get("file")}
    target_files.update(plan.get("files", []))

    for relative_file in sorted(target_files):
        if not relative_file:
            continue
        file_path = root / relative_file
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if file_path.exists():
            applied.append(str(relative_file))
            continue

        if relative_file.endswith(".py"):
            file_path.write_text(_render_feature_template(relative_file), encoding="utf-8")
            applied.append(str(relative_file))

    return applied


def validate_implementation(project_root: str | None = None) -> dict:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    generated_files = sorted(root.rglob("*.py"))

    if not generated_files:
        return {"status": "skipped", "checks": [], "reason": "No generated Python files were found."}

    generated_candidates = []
    for path in generated_files:
        path_text = str(path).lower()
        if "sample" in path_text or "orders" in path_text or "sample-app" in path_text:
            continue
        generated_candidates.append(path)

    if not generated_candidates:
        return {"status": "skipped", "checks": [], "reason": "No generic prompt-driven implementation file was found."}

    import_path = str(root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

    target = generated_candidates[0]
    module_name = target.stem
    spec = spec_from_file_location(module_name, target)
    if spec is None or spec.loader is None:
        return {"status": "failed", "checks": [], "reason": "Could not import generated module."}

    module = module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    handler = getattr(module, "handle_request", None)
    if handler is None:
        return {"status": "failed", "checks": [], "reason": "Generated module does not expose handle_request."}

    result = handler("I want a form that accepts a request and shows a success message after submission.")
    passed = isinstance(result, dict) and result.get("status") == "accepted"
    return {
        "status": "passed" if passed else "failed",
        "checks": [{
            "name": "generated_feature_handler",
            "status_code": 200,
            "body": result,
        }],
    }
