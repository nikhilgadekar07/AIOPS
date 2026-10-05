import json

from sqlmodel import Session, select

from orchestrator.entities import Spec


def save_spec(session: Session, requirement_id: str, content: dict) -> Spec:
    existing = session.exec(
        select(Spec).where(Spec.requirement_id == requirement_id)
    ).all()
    version = len(existing) + 1
    spec = Spec(
        requirement_id=requirement_id,
        version=version,
        content_json=json.dumps(content),
    )
    session.add(spec)
    session.commit()
    session.refresh(spec)
    return spec


def latest_spec(session: Session, requirement_id: str) -> Spec | None:
    specs = session.exec(
        select(Spec).where(Spec.requirement_id == requirement_id)
    ).all()
    return max(specs, key=lambda s: s.version) if specs else None
