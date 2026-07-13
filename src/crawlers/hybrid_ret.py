"""
Hybrid Retriever
------------------
Combines dense embeddings (meaning-based) and BM25 (keyword-based) into one
ranked result list using Reciprocal Rank Fusion (RRF) — a standard way to
merge two differently-scaled ranking methods without needing to normalize
their raw scores against each other.

Also adds an exact circular-number match boost: if the query itself looks
like a specific reference ("BPRD Circular No. 17 of 2024"), any chunk whose
extracted metadata exactly matches that reference gets boosted to the top —
this directly addresses the ambiguity noted when testing BM25 alone, where
"No. 17 of 2024" and "No. 18 of 2024" scored closely together on token
overlap alone.

Known limitation: metadata filtering by department works (exact match on
the `department` field). Filtering by year does not yet work as a precise
filter, since only a full `date` string was stored in Chroma's metadata,
not a separate `year` field — worth adding later if department+year
combined filtering becomes something you need often.

Requirements:
    pip install chromadb sentence-transformers rank_bm25

Usage:
    python hybrid_retriever.py
"""

import os
import re
import pickle
import chromadb

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - optional fallback for constrained environments
    SentenceTransformer = None

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))  # adjust if your layout differs

VECTOR_DB_DIR = os.path.join(PROJECT_ROOT, "data", "vector_db")
BM25_INDEX_PATH = os.path.join(PROJECT_ROOT, "data", "bm25_index.pkl")
COLLECTION_NAME = "sbp_circulars"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

RRF_K = 60             # standard smoothing constant for reciprocal rank fusion
TOP_K_PER_METHOD = 20   # how many candidates each method contributes before fusion
FINAL_TOP_N = 5
EXACT_MATCH_BOOST = 1.0  # large relative to typical RRF scores (~0.03 per rank), guarantees the exact match wins
RETRIEVAL_MODE = os.environ.get("SBP_RETRIEVAL_MODE", "hybrid").strip().lower()

TOKEN_PATTERN = re.compile(r"\w+")
CIRCULAR_QUERY_PATTERN = re.compile(
    r"([A-Za-z0-9&\-]+)\s+Circular(?:\s+Letter)?\s*No\.?\s*(\d+)\s*(?:of\s*(\d{4}))?",
    re.IGNORECASE,
)


def tokenize(text):
    return TOKEN_PATTERN.findall(text.lower())


class HybridRetriever:
    def __init__(self):
        print("Loading BM25 index...")
        with open(BM25_INDEX_PATH, "rb") as f:
            data = pickle.load(f)
        self.bm25 = data["bm25"]
        self.chunks = data["chunks"]
        self.chunk_id_to_idx = {c["chunk_id"]: i for i, c in enumerate(self.chunks)}

        self.use_dense = RETRIEVAL_MODE != "bm25"
        self.model = None
        if self.use_dense and SentenceTransformer is not None:
            print("Loading embedding model...")
            self.model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        elif self.use_dense:
            print("Dense retriever unavailable; falling back to BM25-only mode.")
            self.use_dense = False
        else:
            print("Using BM25-only retrieval mode.")

        print("Connecting to vector DB...")
        client = chromadb.PersistentClient(path=VECTOR_DB_DIR)
        self.collection = client.get_or_create_collection(name=COLLECTION_NAME)

        print(f"Retriever ready ({'hybrid' if self.use_dense else 'bm25-only'} mode).\n")

    def _dense_search(self, query, top_k, department=None):
        where = {"department": department.upper()} if department else None
        query_embedding = self.model.encode(QUERY_PREFIX + query, normalize_embeddings=True)
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=where,
        )
        return results["ids"][0] if results["ids"] else []

    def _bm25_search(self, query, top_k, department=None):
        tokenized_query = tokenize(query)
        scores = self.bm25.get_scores(tokenized_query)
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        result_ids = []
        for i in ranked_idx:
            chunk = self.chunks[i]
            if department and chunk.get("department", "").upper() != department.upper():
                continue
            result_ids.append(chunk["chunk_id"])
            if len(result_ids) >= top_k:
                break
        return result_ids

    def _detect_exact_circular_reference(self, query):
        m = CIRCULAR_QUERY_PATTERN.search(query)
        if not m:
            return None
        department, number, year = m.group(1).upper(), m.group(2), m.group(3)
        return {"department": department, "number": number.lstrip("0") or "0", "year": year}

    def search(self, query, top_n=FINAL_TOP_N, department=None, truncate=True):
        dense_ids = self._dense_search(query, TOP_K_PER_METHOD, department=department) if self.use_dense else []
        bm25_ids = self._bm25_search(query, TOP_K_PER_METHOD, department=department)

        fused_scores = {}
        for rank, cid in enumerate(dense_ids):
            fused_scores[cid] = fused_scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)
        for rank, cid in enumerate(bm25_ids):
            fused_scores[cid] = fused_scores.get(cid, 0) + 1.0 / (RRF_K + rank + 1)

        exact_ref = self._detect_exact_circular_reference(query)
        if exact_ref:
            for cid in fused_scores:
                chunk = self.chunks[self.chunk_id_to_idx[cid]]
                cn = (chunk.get("circular_number") or "").upper()
                dept_match = exact_ref["department"] in cn
                number_match = re.search(r"\bNO\.?\s*0*" + re.escape(exact_ref["number"]) + r"\b", cn) is not None
                year_match = exact_ref["year"] is None or exact_ref["year"] in cn
                if dept_match and number_match and year_match:
                    fused_scores[cid] += EXACT_MATCH_BOOST

        ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

        results = []
        for cid, score in ranked:
            chunk = self.chunks[self.chunk_id_to_idx[cid]]
            results.append({
                "chunk_id": cid,
                "score": round(score, 4),
                "circular_number": chunk.get("circular_number", ""),
                "department": chunk.get("department", ""),
                "date": chunk.get("date", ""),
                "title": chunk.get("title", ""),
                "text": chunk["text"][:200] if truncate else chunk["text"],
            })
        return results



def print_results(query, results):
    print(f"\n=== Query: \"{query}\" ===")
    for i, r in enumerate(results, start=1):
        print(f"\n{i}. {r['chunk_id']}  (fused score: {r['score']})")
        print(f"   {r['circular_number']}  |  {r['department']}  |  {r['date']}")
        print(f"   {r['title']}")
        print(f"   {r['text']}")


if __name__ == "__main__":
    retriever = HybridRetriever()

    print_results("public holiday", retriever.search("public holiday"))

    print_results(
        "BPRD Circular No. 17 of 2024",
        retriever.search("BPRD Circular No. 17 of 2024"),
    )

    print_results(
        "what are the rules for foreign currency accounts",
        retriever.search("what are the rules for foreign currency accounts"),
    )