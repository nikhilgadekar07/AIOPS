"""Prepares a local folder holding the codebase a requirement targets.
new      -> empty folder, scaffolded later by the code agent
existing -> cloned from GitHub, copied from a local folder, or unzipped from a local .zip
"""
import json
import shutil
import subprocess
import zipfile
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent / "workspace"


def prepare_new(requirement_id: str) -> str:
    path = WORKSPACE_ROOT / requirement_id
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def prepare_from_github(requirement_id: str, repo_url: str) -> str:
    path = WORKSPACE_ROOT / requirement_id
    if path.exists():
        shutil.rmtree(path)
    subprocess.run(["git", "clone", repo_url, str(path)], check=True)
    return str(path)


def prepare_from_zip(requirement_id: str, zip_path: str) -> str:
    path = WORKSPACE_ROOT / requirement_id
    path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(path)
    return str(path)


def prepare_from_local(requirement_id: str, location: str) -> str:
    source = Path(location).expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"Local code path does not exist: {source}")

    if source.is_file() and source.suffix.lower() == ".json":
        try:
            result = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            result = {}
        workspace_path = result.get("workspace_path") if isinstance(result, dict) else None
        if workspace_path:
            referenced_workspace = Path(workspace_path).expanduser().resolve()
            if referenced_workspace.is_dir():
                source = referenced_workspace

    if source.is_file():
        source = source.parent
    if not source.is_dir():
        raise NotADirectoryError(f"Local code path is not a directory: {source}")

    destination = WORKSPACE_ROOT / requirement_id
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__", "node_modules"),
    )
    return str(destination)
