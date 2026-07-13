"""
Dense Embedding Index Builder
-------------------------------
Embeds every chunk's text_with_context (not the raw text — the whole point
of the contextual prefix step was to enrich what gets embedded) using a
local sentence-transformers model, and stores vectors + metadata in a
persistent ChromaDB collection.

Model choice: BAAI/bge-small-en-v1.5 — a strong, fast, genuinely small
(~130MB) general-purpose English embedding model that runs comfortably on
CPU. Good default for a corpus this size (1471 chunks); swap for a bigger
model later only if retrieval quality testing shows it's actually needed.

Requirements:
    pip install sentence-transformers chromadb

Usage:
    python build_embeddings.py

Input:
    data/chunks_contextualized.jsonl

Output:
    data/vector_db/   (persistent ChromaDB store)
"""

import os
import json
from sentence_transformers import SentenceTransformer
import chromadb

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

CHUNKS_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks_contextualized.jsonl")
VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "data", "vector_db")

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
COLLECTION_NAME = "sbp_circulars"
BATCH_SIZE = 32

# bge models are trained to expect a query-side instruction prefix at
# search time (NOT at indexing time) — noting this now so it isn't
# forgotten when we build the retrieval script later.
# Passages are embedded as-is; queries should be prefixed with:
#   "Represent this sentence for searching relevant passages: "


def load_chunks():
    with open(CHUNKS_JSONL, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def run():
    print(f"Loading embedding model: {EMBEDDING_MODEL_NAME} (first run downloads it, ~130MB)")
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks")

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()
    print(f"Already indexed: {len(existing_ids)} chunks (will be skipped)")

    to_process = [c for c in chunks if c["chunk_id"] not in existing_ids]
    print(f"To embed this run: {len(to_process)}")

    for i in range(0, len(to_process), BATCH_SIZE):
        batch = to_process[i:i + BATCH_SIZE]

        texts = [c["text_with_context"] for c in batch]
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

        ids = [c["chunk_id"] for c in batch]
        documents = [c["text_with_context"] for c in batch]
        metadatas = [
            {
                "doc_id": c["doc_id"],
                "department": c.get("department", "") or "",
                "circular_number": c.get("circular_number", "") or "",
                "date": c.get("date", "") or "",
                "title": c.get("title", "") or "",
                "chunk_index": c["chunk_index"],
                "total_chunks": c["total_chunks"],
            }
            for c in batch
        ]

        collection.add(
            ids=ids,
            embeddings=embeddings.tolist(),
            documents=documents,
            metadatas=metadatas,
        )

        done = min(i + BATCH_SIZE, len(to_process))
        print(f"  ...{done} / {len(to_process)} embedded")

    print(f"\nDone. Total chunks in collection: {collection.count()}")
    print(f"Vector DB stored at: {VECTOR_DB_DIR}")


if __name__ == "__main__":
    run()