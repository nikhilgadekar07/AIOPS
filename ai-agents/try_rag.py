"""End-to-end RAG test, standalone:
1. Ingest a workspace (an existing-project requirement's cloned repo)
2. Retrieve chunks relevant to that requirement's text
3. Generate a spec that uses those chunks as grounding

Run from the repo root:
    .\\.venv\\Scripts\\python.exe .\\ai-agents\\try_rag.py REQ-00X
Replace REQ-00X with a requirement_id that has project_mode == "existing"
and a real workspace_path already on disk (from run_requirement.py).
"""
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


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python try_rag.py <requirement_id>")
    requirement_id = sys.argv[1]

    with Session(engine) as session:
        req = session.exec(
            select(Requirement).where(Requirement.requirement_id == requirement_id)
        ).first()
        if not req:
            sys.exit(f"{requirement_id} not found in the database.")
        if req.project_mode != "existing" or not req.workspace_path:
            sys.exit(f"{requirement_id} has no existing-project workspace to ingest.")

        print(f"Ingesting workspace: {req.workspace_path}")
        count = ingest_workspace(requirement_id, req.workspace_path)
        print(f"Ingested {count} chunks.\n")

        print("Retrieving chunks relevant to the requirement...")
        resolved_text = "\n\n".join(
            f"Q: {q.question}\nA: {q.answer or q.assumed_default}"
            for q in session.exec(
                select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
            ).all()
        )
        query = "\n\n".join([req.title, req.raw_text, resolved_text])
        chunks = retrieve_context(requirement_id, query, top_k=5)
        print(f"Retrieved {len(chunks)} chunks:\n")
        for c in chunks:
            print(f"  - {c['file_path']} (lines {c['start_line']}-{c['end_line']})")

        questions = session.exec(
            select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
        ).all()
        resolved = [
            {"question": q.question, "answer": q.answer or q.assumed_default}
            for q in questions
        ]

        print("\nGenerating spec grounded in retrieved code...")
        spec = generate_spec(req.title, req.raw_text, resolved, codebase_chunks=chunks)

        print("\n--- Grounded spec ---")
        print(json.dumps(spec, indent=2))


if __name__ == "__main__":
    main()
