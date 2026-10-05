import json
import sys

sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select

from agents.spec_agent import generate_spec
from orchestrator.db import engine, init_db
from orchestrator.entities import ClarifyingQuestion, Requirement
from orchestrator.spec_store import latest_spec, save_spec


init_db()


def build_resolved(session: Session, requirement_id: str) -> list[dict]:
    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
    ).all()
    return [
        {"question": q.question, "answer": q.answer or q.assumed_default}
        for q in questions
    ]


def run_spec_stage(session: Session, req: Requirement, feedback: str | None = None):
    resolved = build_resolved(session, req.requirement_id)
    description = req.raw_text
    if feedback:
        description += f"\n\nAdditional feedback from reviewer: {feedback}"
    content = generate_spec(req.title, description, resolved)
    return save_spec(session, req.requirement_id, content)


def main():
    requirement_id = input("Requirement ID (e.g. REQ-001): ").strip()

    with Session(engine) as session:
        req = session.exec(
            select(Requirement).where(Requirement.requirement_id == requirement_id)
        ).first()
        if not req:
            print("Requirement not found.")
            return

        spec = latest_spec(session, requirement_id)
        if not spec:
            spec = run_spec_stage(session, req)

        while True:
            content = json.loads(spec.content_json)
            print(f"\n--- Spec v{spec.version} (confidence: {content.get('confidence')}) ---")
            print(json.dumps(content, indent=2))

            decision = input("\napprove / modify / reject: ").strip().lower()

            if decision == "approve":
                req.status = "approved"
                session.add(req)
                session.commit()
                print("Approved.")
                break
            elif decision == "reject":
                req.status = "rejected"
                session.add(req)
                session.commit()
                print("Rejected.")
                break
            elif decision == "modify":
                feedback = input("What should change? ")
                spec = run_spec_stage(session, req, feedback=feedback)
            else:
                print("Type approve, modify, or reject.")


if __name__ == "__main__":
    main()
