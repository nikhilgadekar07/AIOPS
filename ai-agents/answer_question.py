import sys
sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select
from orchestrator.db import engine
from orchestrator.entities import ClarifyingQuestion

with Session(engine) as session:
    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == "REQ-001")
    ).all()

    for i, q in enumerate(questions):
        status = "answered" if q.answer else "unanswered"
        print(f"[{4}] ({status}) {q.question}")

    choice = int(input("\nWhich question number do you want to answer? "))
    answer_text = input("Your answer: ")

    target = questions[choice]
    target.answer = answer_text
    session.add(target)
    session.commit()

    print(f"\nSaved answer for: {target.question}")