"""Given a requirement's text, finds the most relevant code chunks already
ingested for that requirement_id.

This is what the spec agent calls right before generating a spec, when
project_mode == "existing". For "new" projects there's nothing to retrieve,
so callers should pass an empty list of chunks in that case.
"""
from common.llm_client import embed
from rag.store import get_collection


def retrieve_context(requirement_id: str, query_text: str, top_k: int = 5) -> list[dict]:
    collection = get_collection(requirement_id)
    if collection.count() == 0:
        return []

    query_vector = embed(query_text)
    results = collection.query(query_embeddings=[query_vector], n_results=top_k)

    chunks = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(documents, metadatas):
        chunks.append({
            "text": doc,
            "file_path": meta.get("file_path", "unknown"),
            "start_line": meta.get("start_line"),
            "end_line": meta.get("end_line"),
        })
    return chunks


def format_context_for_prompt(chunks: list[dict]) -> str:
    """Turns retrieved chunks into the text block we paste into the spec
    prompt. Kept separate from retrieve_context so the two concerns --
    'find relevant code' and 'format it for an LLM prompt' -- stay testable
    independently."""
    if not chunks:
        return "No existing codebase context available."

    parts = []
    for c in chunks:
        header = f"--- {c['file_path']} (lines {c['start_line']}-{c['end_line']}) ---"
        parts.append(f"{header}\n{c['text']}")
    return "\n\n".join(parts)
