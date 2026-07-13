"""
Verify Embeddings
-------------------
Runs all three checks in one script: collection count, a sample record
inspection, and a real semantic search query — so nothing gets missed by
copy-pasting a partial snippet.

Usage:
    python verify_embeddings.py
"""

import os
import chromadb
from sentence_transformers import SentenceTransformer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))  # adjust if your layout differs

VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "data", "vector_db")
COLLECTION_NAME = "sbp_circulars"


def main():
    print(f"Looking for vector DB at: {VECTOR_DB_DIR}")
    if not os.path.isdir(VECTOR_DB_DIR):
        print("ERROR: that folder doesn't exist. build_embeddings.py hasn't written here, "
              "or PROJECT_ROOT in this script needs adjusting.")
        return

    client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    count = collection.count()
    print(f"\n--- Check 1: Count ---")
    print(f"Total chunks in collection: {count}")
    if count == 0:
        print("ERROR: collection is empty. Something is still pointing at the wrong place.")
        return

    print(f"\n--- Check 2: Sample record ---")
    result = collection.get(limit=1, include=["embeddings", "documents", "metadatas"])
    print("ID:", result["ids"][0])
    print("Metadata:", result["metadatas"][0])
    print("Document text (first 200 chars):", result["documents"][0][:200])
    print("Embedding length:", len(result["embeddings"][0]))
    print("First 5 embedding values:", result["embeddings"][0][:5])

    print(f"\n--- Check 3: Real query test ---")
    print("Loading embedding model (BAAI/bge-small-en-v1.5)...")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    query = "Represent this sentence for searching relevant passages: public holiday"
    query_embedding = model.encode(query, normalize_embeddings=True)

    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=3,
    )

    for i, doc_id in enumerate(results["ids"][0]):
        print(f"\n{i + 1}. {doc_id}")
        print("   Metadata:", results["metadatas"][0][i])
        print("   Text:", results["documents"][0][i][:150])


if __name__ == "__main__":
    main()