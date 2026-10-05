import sys

sys.path.insert(0, "ai-agents")

from sqlmodel import Session, select

from orchestrator.db import engine, init_db
from orchestrator.entities import ClarifyingQuestion, Requirement
from agents.ambiguity_agent import detect_ambiguities
from input_adapter.workspace import prepare_from_github, prepare_from_zip, prepare_new


init_db()


def next_requirement_id(session: Session) -> str:
    count = len(session.exec(select(Requirement)).all())
    return f"REQ-{count + 1:03d}"


def main():
    title = input("Requirement title: ")
    description = input("Describe what you want: ")
    mode = input("Is this a NEW project or an EXISTING one? [new/existing]: ").strip().lower()

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

        questions = detect_ambiguities(title, description)

        req = Requirement(
            requirement_id=requirement_id,
            title=title,
            raw_text=description,
            source="cli",
            project_mode=mode,
            repo_url=repo_url,
            workspace_path=workspace_path,
        )
        session.add(req)
        for q in questions:
            session.add(
                ClarifyingQuestion(
                    requirement_id=requirement_id,
                    question=q["question"],
                    assumed_default=q["assumed_default"],
                )
            )
        session.commit()

        print(f"\nSaved {requirement_id}")
        print(f"Mode: {mode}")
        print(f"Workspace: {workspace_path}")
        print(f"Questions found: {len(questions)}")


if __name__ == "__main__":
    main()
