import sys
sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select
from orchestrator.db import engine
from orchestrator.entities import Requirement, ClarifyingQuestion
from agents.spec_agent import generate_spec

with Session(engine) as session:
    req = session.exec(
        select(Requirement).where(Requirement.requirement_id == "REQ-001")
    ).first()

    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == "REQ-001")
    ).all()

    resolved = [
        {"question": q.question, "answer": q.answer or q.assumed_default}
        for q in questions
    ]

    spec = generate_spec(req.title, req.raw_text, resolved)
    print(spec)