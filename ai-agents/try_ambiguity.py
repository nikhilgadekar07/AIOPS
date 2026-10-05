import sys
sys.path.insert(0, "ai-agents")

from sqlmodel import Session
from orchestrator.db import engine, init_db
from orchestrator.entities import Requirement, ClarifyingQuestion
from agents.ambiguity_agent import detect_ambiguities

init_db()

title = "Cancel order"
description = "Allow users to cancel a pending order"
questions = detect_ambiguities(title, description)

with Session(engine) as session:
    req = Requirement(requirement_id="REQ-001", title=title, raw_text=description)
    session.add(req)

    for q in questions:
        session.add(ClarifyingQuestion(
            requirement_id="REQ-001",
            question=q["question"],
            assumed_default=q["assumed_default"],
        ))

    session.commit()

print("Saved REQ-001 with", len(questions), "questions.")