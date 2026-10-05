import sys

sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select

from orchestrator.db import engine
from orchestrator.entities import ClarifyingQuestion, Requirement

with Session(engine) as session:
    requirements = session.exec(select(Requirement)).all()
    print(f"Requirements found: {len(requirements)}")

    for req in requirements:
        print(f"\nRequirement: {req.requirement_id}")
        print(f"  title: {req.title}")
        print(f"  mode: {req.project_mode}")
        print(f"  workspace: {req.workspace_path}")
        print(f"  repo_url: {req.repo_url}")

        questions = session.exec(
            select(ClarifyingQuestion).where(
                ClarifyingQuestion.requirement_id == req.requirement_id
            )
        ).all()
        print(f"  questions: {len(questions)}")
        for q in questions:
            print(f"    - {q.question} -> {q.assumed_default}")