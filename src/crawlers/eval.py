"""
Phase 5 — Evaluation Set
--------------------------
Runs a batch of hand-written test questions through the full Phase 4
pipeline (retrieval -> sufficiency check -> generation/refusal) and scores
the one thing that can be objectively automated: did it answer when it
should have, and refuse when it shouldn't have.

Question categories:
  - answerable:    strong, direct retrieval evidence expected (confirmed
                   from earlier manual testing in this project)
  - partial:       real but narrow evidence expected (the corpus's amendment-
                   style circulars won't comprehensively cover a broad
                   question, but should still produce an honest partial
                   answer, not a refusal)
  - unanswerable:  genuinely out-of-scope, no relevant evidence should exist

Scoring is intentionally simple and honest:
  - answerable / partial -> PASS if the system answered (didn't refuse)
  - unanswerable         -> PASS if the system refused

This does NOT automatically judge answer *quality* (e.g. whether a partial
answer correctly identifies what's missing, or whether sources are fully
accurate) — that still needs a human read of the logged output. The script
flags this explicitly rather than pretending a keyword heuristic can judge
quality reliably.

Usage:
    python run_eval.py

Output:
    Console summary table
    data/eval_results.jsonl  (full logged output per question, for review)
"""

import json
import os
import re
from hybrid_retriever import HybridRetriever
from rag_answer import answer_question

os.environ["SBP_RETRIEVAL_MODE"] = "bm25"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))  # adjust if your layout differs
RESULTS_PATH = os.path.join(PROJECT_ROOT, "data", "eval_results.jsonl")

EVAL_SET = [
    # --- answerable: strong, direct evidence confirmed earlier in this project ---
    {"query": "What does BPRD Circular No. 20 of 2024 say about CCTV operations?",
     "category": "answerable"},
    {"query": "What was announced about replacing LIBOR with a relevant benchmark rate?",
     "category": "answerable"},
    {"query": "What is SBP's Clean Note Policy about?",
     "category": "answerable"},
    {"query": "What is announced in BPD Circular No. 14 of 2002?",
     "category": "answerable"},
    {"query": "What should banks do with erroneously received crossed cheques according to BPD Circular Letter No. 22 of 2002?",
     "category": "answerable"},
    {"query": "What is the branch licensing policy in BPD Circular No. 36 of 2002?",
     "category": "answerable"},
    {"query": "What does BPD Circular No. 37 of 2002 clarify about write-off of irrecoverable loans and advances?",
     "category": "answerable"},
    {"query": "What does BPD Circular No. 15 of 2002 say about ineligibility to act as director of a bank or NBFI?",
     "category": "answerable"},
    {"query": "What does BPD Circular No. 20 of 2002 require for banks that are not connected to either ATM switch network?",
     "category": "answerable"},

    # --- partial: real but narrow amendment-level evidence expected ---
    {"query": "What are the rules for foreign currency business value accounts?",
     "category": "partial"},
    {"query": "What are the prudential regulations for microfinance banks?",
     "category": "partial"},
    {"query": "What is the credit policy for housing finance?",
     "category": "partial"},
    {"query": "What does AC&MFD Circular No. 02 of 2022 change about unsecured financing limits and audited financial statements?",
     "category": "partial"},
    {"query": "What does ACFID Circular No. 01 of 2024 change about prudential regulations for agriculture financing?",
     "category": "partial"},

    # --- unanswerable: genuinely outside this corpus's scope ---
    {"query": "What is the current interest rate policy of the US Federal Reserve?",
     "category": "unanswerable"},
    {"query": "What is the price of gold today?",
     "category": "unanswerable"},
    {"query": "Who is the current Prime Minister of Pakistan?",
     "category": "unanswerable"},
    {"query": "What are the cryptocurrency trading regulations in the United States?",
     "category": "unanswerable"},
]

REFUSAL_PATTERNS = (
    r"\bi don't have enough information\b",
    r"\bi do not have enough information\b",
    r"\bnot enough information\b",
    r"\bcannot provide\b",
    r"\bcannot answer\b",
    r"\bi can't answer\b",
    r"\bi cannot answer\b",
    r"\bi'm unable\b",
    r"\bunable to answer\b",
    r"\bno information available\b",
)


def looks_like_refusal(answer_text):
    normalized = answer_text.strip().lower()
    return any(re.search(pattern, normalized) for pattern in REFUSAL_PATTERNS)


def score(category, answered, answer_text):
    expected_answer = category in ("answerable", "partial")
    refusal_like = looks_like_refusal(answer_text)

    if expected_answer:
        return answered and not refusal_like

    return (not answered) or refusal_like


def run():
    retriever = HybridRetriever()
    results = []

    for item in EVAL_SET:
        query, category = item["query"], item["category"]
        result = answer_question(retriever, query, verbose=False)

        refusal_like = looks_like_refusal(result["answer"])
        passed = score(category, result["answered"], result["answer"])
        results.append({
            "query": query,
            "category": category,
            "answered": result["answered"],
            "refusal_like": refusal_like,
            "passed": passed,
            "answer": result["answer"],
            "citation_issues": result.get("citation_issues", []),
            "sources": result.get("sources", ""),
        })

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n{'=' * 90}")
    print(f"{'CATEGORY':<14}{'PASS':<7}{'ANSWERED':<11}{'REFUSAL':<9}QUERY")
    print(f"{'=' * 90}")
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"{r['category']:<14}{status:<7}{str(r['answered']):<11}{str(r['refusal_like']):<9}{r['query'][:55]}")

    total = len(results)
    passed_count = sum(r["passed"] for r in results)
    print(f"\n{passed_count}/{total} passed automated scoring")

    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n{len(failed)} FAILED CASE(S) — needs review:")
        for r in failed:
            print(f"\n  Query: {r['query']}")
            print(f"  Category: {r['category']} | Answered: {r['answered']}")
            print(f"  Answer/refusal text: {r['answer'][:200]}")

    print(f"\nFull results saved to: {RESULTS_PATH}")
    print("\nNOTE: PASS here only means 'answered vs refused' matched expectations.")
    print("Partial-category answers still need a human read of the actual answer text")
    print("(in the JSONL file) to judge whether the caveat/coverage is actually accurate.")


if __name__ == "__main__":
    run()