import json
import sys

sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select

from agents.spec_agent import generate_spec
from orchestrator.db import engine, init_db
from orchestrator.entities import ClarifyingQuestion, Requirement
from orchestrator.spec_store import latest_spec, save_spec
from rag.ingest import ingest_workspace
from rag.retriever import retrieve_context


init_db()


def build_resolved(session: Session, requirement_id: str) -> list[dict]:
    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
    ).all()
    return [
        {"question": q.question, "answer": q.answer or q.assumed_default}
        for q in questions
    ]


def retrieve_codebase_chunks(req: Requirement, requirement_text: str) -> list[dict]:
    if req.project_mode != "existing" or not req.workspace_path:
        return []
    try:
        ingest_workspace(req.requirement_id, req.workspace_path)
    except Exception:
        return []

    resolved = []
    with Session(engine) as session:
        questions = session.exec(
            select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == req.requirement_id)
        ).all()
        resolved = [
            f"Q: {q.question}\nA: {q.answer or q.assumed_default}"
            for q in questions
        ]

    query = "\n\n".join([req.title, requirement_text, *resolved])
    return retrieve_context(req.requirement_id, query, top_k=5)


def run_spec_stage(session: Session, req: Requirement, feedback: str | None = None):
    resolved = build_resolved(session, req.requirement_id)
    description = req.raw_text
    if feedback:
        description += f"\n\nAdditional feedback from reviewer: {feedback}"
    codebase_chunks = retrieve_codebase_chunks(req, description)
    content = generate_spec(req.title, description, resolved, codebase_chunks=codebase_chunks)
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
            review_status = content.get("review_status") or (
                "needs careful review" if float(content.get("confidence") or 0.0) < 0.75 else "moderate confidence"
            )
            print(f"\n--- Spec v{spec.version} (confidence: {content.get('confidence')} / {review_status}) ---")
            print(json.dumps(content, indent=2))

            if review_status == "needs careful review":
                print("Review note: this spec should be checked carefully before approval.")

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
