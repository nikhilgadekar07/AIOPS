import json
import sys

sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select

from agents.spec_agent import generate_spec
from orchestrator.db import engine, init_db
from orchestrator.entities import ClarifyingQuestion, Requirement
from rag.ingest import ingest_workspace
from rag.retriever import retrieve_context


init_db()


def build_query(req: Requirement, session: Session) -> str:
    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == req.requirement_id)
    ).all()
    resolved = "\n\n".join(
        f"Q: {q.question}\nA: {q.answer or q.assumed_default}"
        for q in questions
    )
    return "\n\n".join([req.title, req.raw_text, resolved])


def main():
    requirement_id = sys.argv[1] if len(sys.argv) > 1 else "REQ-002"

    with Session(engine) as session:
        req = session.exec(
            select(Requirement).where(Requirement.requirement_id == requirement_id)
        ).first()
        if req is None:
            print(f"Requirement {requirement_id} not found.")
            return

        print(f"Requirement: {req.requirement_id} | {req.title} | mode={req.project_mode}")
        print(f"Workspace: {req.workspace_path}")

        if req.project_mode != "existing" or not req.workspace_path:
            print("This requirement is not an existing-project run. Nothing to ingest.")
            return

        collection = __import__("rag.store", fromlist=["get_collection"]).get_collection(req.requirement_id)
        if collection.count() == 0:
            count = ingest_workspace(req.requirement_id, req.workspace_path)
            print(f"Ingested chunks: {count}")
        else:
            print(f"Using cached collection for {req.requirement_id}.")

        query = build_query(req, session)
        chunks = retrieve_context(req.requirement_id, query, top_k=3)
        print(f"Retrieved chunks: {len(chunks)}")
        for chunk in chunks:
            print(f"  - {chunk['file_path']} ({chunk['start_line']}-{chunk['end_line']})")

        resolved = [
            {"question": q.question, "answer": q.answer or q.assumed_default}
            for q in session.exec(
                select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == req.requirement_id)
            ).all()
        ]

        spec = generate_spec(req.title, req.raw_text, resolved, codebase_chunks=chunks)
        print("\nReview status:", spec.get("review_status"))
        print("Confidence:", spec.get("confidence"))
        print("Impact analysis:", json.dumps(spec.get("impact_analysis", []), indent=2))
        print("Function confidence:", json.dumps(spec.get("function_confidence", []), indent=2))
        print("Critique:", json.dumps(spec.get("critique", {}), indent=2))
        print("\nFinal spec keys:", sorted(spec.keys()))


if __name__ == "__main__":
    main()
