from typing import Optional

from sqlmodel import Field, SQLModel


class Requirement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: str = Field(index=True, unique=True)
    title: str
    raw_text: str
    status: str = "created"


class ClarifyingQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: str = Field(index=True)
    question: str
    assumed_default: str
    answer: Optional[str] = None
