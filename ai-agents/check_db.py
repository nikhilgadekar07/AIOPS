import sys
sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select
from orchestrator.db import engine
from orchestrator.entities import Requirement, ClarifyingQuestion

with Session(engine) as session:
    req = session.exec(
        select(Requirement).where(Requirement.requirement_id == "REQ-001")
    ).first()
    print("Requirement:", req)

    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == "REQ-001")
    ).all()
    print(f"\n{len(questions)} questions:")
    for q in questions:
        print("-", q.question)