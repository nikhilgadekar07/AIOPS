from sqlmodel import SQLModel, create_engine

from orchestrator.entities import ClarifyingQuestion, Requirement

engine = create_engine("sqlite:///forgeflow.db")


def init_db():
    SQLModel.metadata.create_all(engine)