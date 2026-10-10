import json
import sys
from pathlib import Path

sys.path.insert(0, "ai-agents")

from agents.implementation_agent import (
    apply_implementation_plan,
    generate_implementation_plan,
    validate_implementation,
)
from orchestrator.db import engine, init_db
from orchestrator.entities import Requirement, Spec
from sqlmodel import Session, select


init_db()


def load_latest_spec(requirement_id: str) -> tuple[Requirement | None, dict | None]:
    with Session(engine) as session:
        req = session.exec(
            select(Requirement).where(Requirement.requirement_id == requirement_id)
        ).first()
        if req is None:
            return None, None

        spec_row = session.exec(
            select(Spec)
            .where(Spec.requirement_id == requirement_id)
            .order_by(Spec.version.desc())
        ).first()
        if spec_row is None:
            return req, None

        return req, json.loads(spec_row.content_json)


def main():
    requirement_id = sys.argv[1] if len(sys.argv) > 1 else "REQ-002"
    req, spec = load_latest_spec(requirement_id)

    if req is None:
        print(f"Requirement {requirement_id} not found.")
        return

    if spec is None:
        print(f"No saved spec found for {requirement_id}; generating a fallback implementation plan.")
        spec = {
            "functional_requirements": [
                f"Implement the requirement for {req.title}.",
            ],
            "affected_components": ["orders API", "app routing"],
            "api_changes": ["Add or update the relevant endpoint."],
            "database_changes": [],
            "confidence": 0.75,
        }

    plan = generate_implementation_plan(req.title, req.raw_text, spec, codebase_chunks=[], use_llm=False)
    print(json.dumps(plan, indent=2))

    project_root = Path(__file__).resolve().parents[1]
    applied = apply_implementation_plan(plan, str(project_root))
    print(f"\nApplied implementation updates: {applied or 'none'}")

    validation = validate_implementation(str(project_root))
    print(f"\nValidation status: {validation['status']}")
    print(json.dumps(validation, indent=2))

    output_dir = Path("ai-agents/workspace")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"implementation_plan_{requirement_id}.json"
    output_path.write_text(json.dumps({"plan": plan, "validation": validation}, indent=2), encoding="utf-8")
    print(f"\nSaved plan to: {output_path}")


if __name__ == "__main__":
    main()
