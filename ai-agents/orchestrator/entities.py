from typing import Optional

from sqlmodel import Field, SQLModel


class Requirement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: str = Field(index=True, unique=True)
    title: str
    raw_text: str
    status: str = "created"
    source: str = "cli"
    project_mode: str = "new"
    repo_url: Optional[str] = None
    workspace_path: Optional[str] = None
    require_human_review: bool = False


class ClarifyingQuestion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: str = Field(index=True)
    question: str
    assumed_default: str
    answer: Optional[str] = None


class Spec(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    requirement_id: str = Field(index=True)
    version: int
    content_json: str
