import json
import sys

sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select

from agents.ambiguity_agent import detect_ambiguities
from agents.spec_agent import generate_spec
from input_adapter.workspace import prepare_from_github, prepare_from_zip, prepare_new
from orchestrator.db import engine, init_db
from orchestrator.entities import ClarifyingQuestion, Requirement
from orchestrator.spec_store import latest_spec, save_spec
from rag.ingest import ingest_workspace
from rag.retriever import retrieve_context


init_db()


def next_requirement_id(session):
    count = len(session.exec(select(Requirement)).all())
    return f"REQ-{count + 1:03d}"


def build_resolved(session, requirement_id):
    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
    ).all()
    return [
        {"question": q.question, "answer": q.answer or q.assumed_default}
        for q in questions
    ]


def retrieve_codebase_chunks(req: Requirement, requirement_text: str):
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


def run_spec_stage(session, req, feedback=None):
    resolved = build_resolved(session, req.requirement_id)
    description = req.raw_text
    if feedback:
        description += f"\n\nAdditional feedback from reviewer: {feedback}"
    codebase_chunks = retrieve_codebase_chunks(req, description)
    content = generate_spec(req.title, description, resolved, codebase_chunks=codebase_chunks)
    return save_spec(session, req.requirement_id, content)


def main():
    title = input("Requirement title: ")
    description = input("Describe what you want: ")
    mode = input("NEW or EXISTING project? [new/existing]: ").strip().lower()

    with Session(engine) as session:
        requirement_id = next_requirement_id(session)

        if mode == "existing":
            location = input("GitHub URL or local .zip path: ").strip()
            if location.endswith(".zip"):
                workspace_path = prepare_from_zip(requirement_id, location)
                repo_url = None
            else:
                workspace_path = prepare_from_github(requirement_id, location)
                repo_url = location
        else:
            mode = "new"
            workspace_path = prepare_new(requirement_id)
            repo_url = None

        req = Requirement(
            requirement_id=requirement_id,
            title=title,
            raw_text=description,
            source="cli",
            project_mode=mode,
            repo_url=repo_url,
            workspace_path=workspace_path,
            status="analyzing",
        )
        session.add(req)
        session.commit()

        questions = detect_ambiguities(title, description)
        for q in questions:
            session.add(
                ClarifyingQuestion(
                    requirement_id=requirement_id,
                    question=q["question"],
                    assumed_default=q["assumed_default"],
                )
            )
        session.commit()

        if questions:
            print(f"\n{len(questions)} questions found. Answer them, or press Enter to accept the default.\n")
            saved_questions = session.exec(
                select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
            ).all()
            for q in saved_questions:
                print(f"Q: {q.question}")
                print(f"   default: {q.assumed_default}")
                answer = input("   your answer (Enter to accept default): ").strip()
                if answer:
                    q.answer = answer
                    session.add(q)
            session.commit()

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
                print(f"\n{requirement_id} approved.")
                break
            elif decision == "reject":
                req.status = "rejected"
                session.add(req)
                session.commit()
                print(f"\n{requirement_id} rejected.")
                break
            elif decision == "modify":
                feedback = input("What should change? ")
                spec = run_spec_stage(session, req, feedback=feedback)
            else:
                print("Type approve, modify, or reject.")


if __name__ == "__main__":
    main()
