"""Splits a codebase into small, embeddable pieces.

Design choices, and why:
- Chunk by a fixed number of LINES, not characters. Code reads naturally in
  lines, and this keeps chunks roughly comparable in size regardless of
  language.
- Overlap chunks slightly (OVERLAP_LINES) so a function split across a chunk
  boundary still appears whole in at least one chunk.
- Skip folders that are never useful to retrieve from: version control,
  virtual envs, dependency folders, caches. Without this, embedding a repo
  would waste time (and in a paid-API world, money) on thousands of
  irrelevant files.
- Skip binary/non-text files by extension, since embedding them is
  meaningless and often crashes on decoding.
"""
from dataclasses import dataclass
from pathlib import Path

CHUNK_LINES = 40
OVERLAP_LINES = 5

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "dist", "build", ".pytest_cache", ".mypy_cache", "workspace",
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".pyc",
    ".db", ".sqlite", ".lock", ".woff", ".woff2", ".ttf",
}

MAX_FILE_SIZE_BYTES = 500_000  # skip unusually large generated files


@dataclass
class Chunk:
    text: str
    file_path: str   # relative to the workspace root
    start_line: int
    end_line: int


def _iter_source_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in relative_parts[:-1]):
            continue
        if path.suffix.lower() in SKIP_EXTENSIONS:
            continue
        if path.stat().st_size > MAX_FILE_SIZE_BYTES:
            continue
        yield path


def chunk_file(path: Path, root: Path) -> list[Chunk]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except (UnicodeDecodeError, PermissionError):
        return []

    if not lines:
        return []

    relative_path = str(path.relative_to(root))
    chunks = []
    start = 0
    while start < len(lines):
        end = min(start + CHUNK_LINES, len(lines))
        text = "\n".join(lines[start:end]).strip()
        if text:
            chunks.append(Chunk(
                text=text, file_path=relative_path,
                start_line=start + 1, end_line=end,
            ))
        if end == len(lines):
            break
        start = end - OVERLAP_LINES
    return chunks


def chunk_workspace(workspace_path: str) -> list[Chunk]:
    root = Path(workspace_path)
    all_chunks: list[Chunk] = []
    for file_path in _iter_source_files(root):
        all_chunks.extend(chunk_file(file_path, root))
    return all_chunks
