"""Turns a workspace folder into searchable chunks: chunk -> embed -> store.

This is the function the intake flow calls once, right after a workspace is
prepared (cloned or unzipped), for project_mode == "existing". A brand-new
empty project has nothing to ingest, so callers should skip this for "new".
"""
from common.llm_client import embed
from rag.chunker import chunk_workspace
from rag.store import get_collection, reset_collection


def ingest_workspace(requirement_id: str, workspace_path: str) -> int:
    reset_collection(requirement_id)
    collection = get_collection(requirement_id)

    chunks = chunk_workspace(workspace_path)
    if not chunks:
        return 0

    ids, embeddings, documents, metadatas = [], [], [], []
    for i, chunk in enumerate(chunks):
        vector = embed(chunk.text)
        ids.append(f"{requirement_id}-{i}")
        embeddings.append(vector)
        documents.append(chunk.text)
        metadatas.append({
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
        })

    # Chroma caps how many items can be added in one call on some setups;
    # batching keeps this working regardless of repo size.
    batch_size = 100
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            embeddings=embeddings[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )

    return len(chunks)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        sys.exit("usage: python rag/ingest.py <requirement_id> <workspace_path>")
    req_id, ws_path = sys.argv[1], sys.argv[2]
    count = ingest_workspace(req_id, ws_path)
    print(f"Ingested {count} chunks for {req_id} from {ws_path}")
