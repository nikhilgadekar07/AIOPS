"""Thin wrapper around Chroma, our local vector database.

One collection per requirement_id, not one giant collection for everything.
Why: each requirement usually targets one codebase (one workspace). Scoping
the collection means a search for REQ-003 can never accidentally return
chunks from REQ-001's unrelated workspace. The isolation is "free" this way,
rather than something we'd have to filter for by hand on every query.
"""
import chromadb

CHROMA_PATH = "ai-agents/chroma_data"

_client = chromadb.PersistentClient(path=CHROMA_PATH)


def _collection_name(requirement_id: str) -> str:
    return f"repo_{requirement_id}"


def get_collection(requirement_id: str):
    return _client.get_or_create_collection(name=_collection_name(requirement_id))


def reset_collection(requirement_id: str) -> None:
    """Deletes and recreates the collection -- used when re-ingesting the
    same requirement's workspace so chunks are never duplicated."""
    name = _collection_name(requirement_id)
    try:
        _client.delete_collection(name=name)
    except Exception:
        pass  # collection may not exist yet on first ingest
