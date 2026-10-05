from sqlmodel import SQLModel, Session, create_engine
from orchestrator.entities import Requirement, ClarifyingQuestion

engine = create_engine("sqlite:///forgeflow.db")


def init_db():
    SQLModel.metadata.create_all(engine)