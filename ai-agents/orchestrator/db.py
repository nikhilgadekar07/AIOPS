from sqlmodel import SQLModel, create_engine

from orchestrator.entities import ClarifyingQuestion, Requirement

engine = create_engine("sqlite:///forgeflow.db")


def init_db():
    SQLModel.metadata.create_all(engine)

    with engine.begin() as conn:
        try:
            columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(requirement)")]
        except Exception:
            return

        if "require_human_review" not in columns:
            conn.exec_driver_sql("ALTER TABLE requirement ADD COLUMN require_human_review BOOLEAN NOT NULL DEFAULT 0")