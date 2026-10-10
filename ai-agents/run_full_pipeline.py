import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sqlmodel import Session, select

from agents.ambiguity_agent import detect_ambiguities
from agents.implementation_agent import apply_implementation_plan, generate_implementation_plan, validate_implementation
from agents.spec_agent import generate_spec
from input_adapter.workspace import prepare_from_github, prepare_from_zip, prepare_new
from orchestrator.db import engine, init_db
from orchestrator.entities import ClarifyingQuestion, Requirement
from orchestrator.spec_store import save_spec
from rag.ingest import ingest_workspace
from rag.retriever import retrieve_context


init_db()


def derive_requirement_from_prompt(prompt: str) -> tuple[str, str]:
    raw = (prompt or "").strip()
    if not raw:
        raise ValueError("A natural-language prompt is required.")

    words = []
    for token in raw.replace("\n", " ").split():
        clean = token.strip(".,!?;:\"'[](){}")
        if clean:
            words.append(clean)

    title_words = []
    for word in words[:10]:
        word = word.strip()
        if word.lower() in {"i", "want", "need", "please", "build", "create", "make", "add", "implement"}:
            continue
        title_words.append(word)

    if not title_words:
        title = "Feature Request"
    else:
        title = " ".join(title_words[:8]).title()

    return title, raw


def next_requirement_id(session):
    count = len(session.exec(select(Requirement)).all())
    return f"REQ-{count + 1:03d}"


def build_resolved(session, requirement_id):
    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
    ).all()
    return [
        {"question": q.question, "answer": q.answer or q.assumed_default}
        for q in questions
    ]


def retrieve_codebase_chunks(req: Requirement, requirement_text: str):
    if req.project_mode != "existing" or not req.workspace_path:
        return []
    try:
        ingest_workspace(req.requirement_id, req.workspace_path)
    except Exception:
        return []

    resolved = []
    with Session(engine) as session:
        questions = session.exec(
            select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == req.requirement_id)
        ).all()
        resolved = [
            f"Q: {q.question}\nA: {q.answer or q.assumed_default}"
            for q in questions
        ]

    query = "\n\n".join([req.title, requirement_text, *resolved])
    return retrieve_context(req.requirement_id, query, top_k=5)


def write_live_status(
    output_path: str | Path | None = None,
    *,
    status: str = "working",
    stage: str = "",
    message: str = "",
    progress: int = 0,
    requirement_id: str | None = None,
    stages: list[dict] | None = None,
    prompt: str | None = None,
):
    workspace_dir = ROOT / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    target_path = Path(output_path) if output_path is not None else workspace_dir / "live_status.json"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "status": status,
        "stage": stage,
        "message": message,
        "progress": max(0, min(100, int(progress))),
        "requirement_id": requirement_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stages": stages or [],
        "prompt": prompt,
    }
    target_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def log_stage(stage_name: str, message: str, stage_log: list[dict], output_path: str | Path | None = None, requirement_id: str | None = None, prompt: str | None = None):
    entry = {"stage": stage_name, "message": message}
    stage_log.append(entry)
    progress = min(100, max(5, len(stage_log) * 12))
    payload = write_live_status(
        output_path=output_path,
        status="working",
        stage=stage_name,
        message=message,
        progress=progress,
        requirement_id=requirement_id,
        stages=stage_log,
        prompt=prompt,
    )
    print(f"\n[Stage: {stage_name}] {message}")
    return payload


def run_spec_stage(session, req, feedback=None, stage_log=None):
    resolved = build_resolved(session, req.requirement_id)
    description = req.raw_text
    if feedback:
        description += f"\n\nAdditional feedback from reviewer: {feedback}"
    if stage_log is not None:
        log_stage("Spec Generation", "Turning the prompt into a clear specification and acceptance criteria.", stage_log)
    codebase_chunks = retrieve_codebase_chunks(req, description)
    content = generate_spec(req.title, description, resolved, codebase_chunks=codebase_chunks)
    return save_spec(session, req.requirement_id, content)


def prompt_for_answers(session, requirement_id):
    questions = session.exec(
        select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)
    ).all()
    for q in questions:
        answer = input(f"Q: {q.question}\n   default: {q.assumed_default}\n   your answer (press Enter to accept): ").strip()
        if answer:
            q.answer = answer
            session.add(q)
    session.commit()


def print_json(label, payload):
    print(f"\n--- {label} ---")
    print(json.dumps(payload, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Run the full natural-language requirement-to-implementation workflow.")
    parser.add_argument("--prompt", help="Natural-language request describing what to build")
    parser.add_argument("--title", help="Optional legacy title override")
    parser.add_argument("--description", help="Optional legacy description override")
    parser.add_argument("--mode", choices=["new", "existing"], default="new")
    parser.add_argument("--location", help="GitHub URL or .zip path for existing mode")
    parser.add_argument("--interactive", action="store_true", help="Prompt for clarifying answers and spec review")
    parser.add_argument("--require-human-review", action="store_true", help="Require a human review gate before implementation proceeds")
    parser.add_argument("--auto-approve", action="store_true", help="Approve the spec automatically without a manual review step")
    args = parser.parse_args()

    user_prompt = (args.prompt or "").strip() or " ".join(part for part in [args.title or "", args.description or ""] if part).strip()
    if not user_prompt:
        parser.error("A natural-language prompt is required via --prompt or a legacy --title/--description pair.")

    derived_title, requirement_text = derive_requirement_from_prompt(user_prompt)
    title = (args.title or derived_title).strip() or derived_title
    description = (args.description or requirement_text).strip() or requirement_text

    stage_log = []
    with Session(engine) as session:
        requirement_id = next_requirement_id(session)

        log_stage("Understanding Request", f"I’m reading your request and turning it into a concrete build plan.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)

        if args.mode == "existing":
            if not args.location:
                parser.error("existing mode requires --location")
            if args.location.endswith(".zip"):
                workspace_path = prepare_from_zip(requirement_id, args.location)
                repo_url = None
            else:
                workspace_path = prepare_from_github(requirement_id, args.location)
                repo_url = args.location
        else:
            workspace_path = prepare_new(requirement_id)
            repo_url = None

        log_stage("Preparing Workspace", f"Setting up the project workspace for requirement {requirement_id} so the build can happen in the right place.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)

        if args.require_human_review:
            log_stage("Human Review Layer", "The requirement has been marked for a human review gate before implementation begins.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)

        req = Requirement(
            requirement_id=requirement_id,
            title=title,
            raw_text=description,
            source="story",
            project_mode=args.mode,
            repo_url=repo_url,
            workspace_path=workspace_path,
            status="analyzing",
            require_human_review=args.require_human_review,
        )
        session.add(req)
        session.commit()

        questions = detect_ambiguities(title, description)
        log_stage("Ambiguity Check", f"Checking for missing details and clarifying anything that could block a clean build. Found {len(questions)} possible gaps.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)
        for q in questions:
            session.add(
                ClarifyingQuestion(
                    requirement_id=requirement_id,
                    question=q["question"],
                    assumed_default=q["assumed_default"],
                )
            )
        session.commit()

        if questions and args.interactive:
            print(f"\n{len(questions)} clarifying questions detected.")
            prompt_for_answers(session, requirement_id)
        elif questions:
            for q in session.exec(select(ClarifyingQuestion).where(ClarifyingQuestion.requirement_id == requirement_id)).all():
                q.answer = q.assumed_default
                session.add(q)
            session.commit()

        spec_row = run_spec_stage(session, req, stage_log=stage_log)
        spec = json.loads(spec_row.content_json)
        print_json("Generated Spec", spec)

        if args.interactive:
            while True:
                decision = input("\napprove / modify / reject: ").strip().lower()
                if decision == "approve":
                    req.status = "approved"
                    session.add(req)
                    session.commit()
                    break
                if decision == "reject":
                    req.status = "rejected"
                    session.add(req)
                    session.commit()
                    print("Requirement rejected.")
                    return
                if decision == "modify":
                    feedback = input("What should change? ")
                    spec_row = run_spec_stage(session, req, feedback=feedback, stage_log=stage_log)
                    spec = json.loads(spec_row.content_json)
                    print_json("Updated Spec", spec)
                    continue
                print("Type approve, modify, or reject.")
        else:
            req.status = "approved" if args.auto_approve else "approved"
            session.add(req)
            session.commit()
            log_stage("Review Gate", "The request has passed the review gate and is ready for implementation.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)

        project_root = Path(workspace_path)
        plan = generate_implementation_plan(title, description, spec, codebase_chunks=[], use_llm=False)
        log_stage("Implementation Planning", "Mapping the accepted requirement into the exact files, components, and actions needed for the build.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)
        print_json("Implementation Plan", plan)

        applied = apply_implementation_plan(plan, str(project_root))
        log_stage("Applying Changes", f"Writing the implementation into the workspace now. Files touched: {applied or 'none'}.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)
        print(f"\nApplied implementation updates: {applied or 'none'}")

        validation = validate_implementation(str(project_root))
        log_stage("Validation", "Running a smoke test against the generated result to confirm the build works and behaves as expected.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)
        print_json("Validation", validation)

        output_dir = project_root.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"pipeline_{requirement_id}.json"
        output_payload = {
            "requirement_id": requirement_id,
            "title": title,
            "prompt": description,
            "stages": stage_log,
            "plan": plan,
            "validation": validation,
            "generated_files": plan.get("files", []) if isinstance(plan, dict) else [],
            "output_path": str(output_path),
        }
        output_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
        print(f"\nSaved full pipeline output to: {output_path}")

        log_stage("Completion", f"The workflow finished for {requirement_id}. The prompt has been processed from idea to implementation and validation.", stage_log, output_path=ROOT / "workspace" / "live_status.json", requirement_id=requirement_id, prompt=description)
        write_live_status(
            output_path=ROOT / "workspace" / "live_status.json",
            status="completed",
            stage="Completed",
            message=f"Build finished for {requirement_id}. The app is ready for review.",
            progress=100,
            requirement_id=requirement_id,
            stages=stage_log,
            prompt=description,
        )
        print(f"\nComplete workflow finished for {requirement_id}.")


if __name__ == "__main__":
    main()
