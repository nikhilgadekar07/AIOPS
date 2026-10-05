"""Prepares a local folder holding the codebase a requirement targets.
new      -> empty folder, scaffolded later by the code agent
existing -> cloned from GitHub, or unzipped from a local .zip
"""
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
