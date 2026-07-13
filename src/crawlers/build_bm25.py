"""
BM25 Keyword Index Builder
----------------------------
Builds a keyword-search index (BM25) over the same text_with_context field
used for embeddings, so retrieval can later combine both: dense search for
meaning, BM25 for exact terms (circular numbers, named entities, specific
amounts) that embeddings sometimes blur over.

Unlike embeddings, BM25 is cheap and fast to build in one shot — no model
download, no per-chunk API/local-inference calls, no need for the
resumability logic the embedding script needed.

Requirements:
    pip install rank_bm25

Usage:
    python build_bm25_index.py

Input:
    data/chunks_contextualized.jsonl

Output:
    data/bm25_index.pkl   (pickled BM25 index + parallel chunk metadata)
"""

import os
import re
import json
import pickle
from rank_bm25 import BM25Okapi

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))  # adjust if your layout differs

CHUNKS_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks_contextualized.jsonl")
BM25_INDEX_PATH = os.path.join(PROJECT_ROOT, "data", "bm25_index.pkl")

TOKEN_PATTERN = re.compile(r"\w+")


def tokenize(text):
    return TOKEN_PATTERN.findall(text.lower())


def load_chunks():
    with open(CHUNKS_JSONL, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def build():
    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks")

    tokenized_corpus = [tokenize(c["text_with_context"]) for c in chunks]
    bm25 = BM25Okapi(tokenized_corpus)

    # store the chunk records alongside the index so search results can be
    # mapped back to doc_id / metadata / original text
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump({"bm25": bm25, "chunks": chunks}, f)

    print(f"BM25 index built over {len(chunks)} chunks")
    print(f"Saved to: {BM25_INDEX_PATH}")
    return bm25, chunks


def demo_query(bm25, chunks, query, top_n=3):
    print(f"\n--- Test query: \"{query}\" ---")
    tokenized_query = tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_n]
    for rank, idx in enumerate(ranked, start=1):
        chunk = chunks[idx]
        print(f"\n{rank}. {chunk['chunk_id']}  (score: {scores[idx]:.2f})")
        print("   Circular:", chunk.get("circular_number", ""))
        print("   Text:", chunk["text"][:150])


if __name__ == "__main__":
    bm25, chunks = build()

    # Two test queries: one that should also work well with embeddings
    # (general topic), one with an exact term that BM25 should nail and
    # embeddings might be fuzzier on.
    demo_query(bm25, chunks, "public holiday")
    demo_query(bm25, chunks, "BPRD Circular No. 17 of 2024")