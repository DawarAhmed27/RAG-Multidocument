"""
Sufficiency Check Diagnostic
------------------------------
Standalone script, independent of whatever state rag_answer.py is
currently in. Retrieves chunks for the FCBVA question, builds the same
sufficiency prompt, and prints the RAW model response with no parsing —
so we can tell apart:
  (a) the model actually saying something like "yes, sufficient" in a
      format the regex parser didn't catch (a parsing bug), from
  (b) the model genuinely reasoning its way to "insufficient" despite
      good evidence (a prompt-design issue).

Usage:
    python diagnose_sufficiency.py
"""

import requests
from hybrid_retriever import HybridRetriever

LM_STUDIO_BASE = "http://localhost:1234"


def get_loaded_model():
    resp = requests.get(f"{LM_STUDIO_BASE}/v1/models", timeout=10)
    resp.raise_for_status()
    models = resp.json().get("data", [])
    if not models:
        raise RuntimeError("No models reported by LM Studio /v1/models — is a model loaded?")
    return models[0]["id"]


def call_lm_studio(model_name, prompt, timeout=180, max_tokens=150):
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    resp = requests.post(f"{LM_STUDIO_BASE}/v1/chat/completions", json=payload, timeout=timeout)
    if not resp.ok:
        print(f"LM Studio returned {resp.status_code}. Response body:")
        print(resp.text)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def format_chunks_for_prompt(chunks):
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(
            f"[{i}] {c['circular_number']} | {c['department']} | {c['date']} | {c['title']}\n"
            f"{c['text']}\n"
        )
    return "\n".join(lines)


SUFFICIENCY_PROMPT_TEMPLATE = """You are evaluating whether the retrieved documents below contain enough information to provide a genuinely useful, evidence-based answer to the user's question.

Mark SUFFICIENT if the documents contain real, specific, on-topic evidence that supports at least a partial, accurate answer — even if they don't cover every possible aspect of the question. Regulatory circulars are often narrow amendments to existing rules, not comprehensive rulebooks, so partial coverage of a specific requirement should still count as sufficient.

Mark INSUFFICIENT only if the documents are off-topic, purely tangential, or contain no real substantive content relevant to the question.

Question: {query}

Retrieved documents:
{formatted_chunks}

Respond in exactly this format, nothing else:
SUFFICIENT: yes or no
REASONING: <one sentence explaining why>"""


def run_one(model_name, retriever, query):
    print(f"\nQuery: {query}")
    chunks = retriever.search(query, top_n=5)
    print(f"Retrieved {len(chunks)} chunks:")
    for c in chunks:
        print(f"  - {c['circular_number']} | {c['title']}")

    prompt = SUFFICIENCY_PROMPT_TEMPLATE.format(
        query=query, formatted_chunks=format_chunks_for_prompt(chunks)
    )
    raw_response = call_lm_studio(model_name, prompt)
    print("\nRAW MODEL RESPONSE:")
    print(raw_response)
    print("-" * 70)


def main():
    print("Detecting loaded LM Studio model...")
    model_name = get_loaded_model()
    print(f"Using model: {model_name}\n")

    print("Loading retriever...")
    retriever = HybridRetriever()

    print("\n" + "=" * 70)
    print("TEST 1: in-scope question with known good evidence")
    print("=" * 70)
    run_one(model_name, retriever, "What are the rules for foreign currency business value accounts?")

    print("\n" + "=" * 70)
    print("TEST 2: genuinely out-of-scope question (should still refuse)")
    print("=" * 70)
    run_one(model_name, retriever, "What is the current interest rate policy of the US Federal Reserve?")


if __name__ == "__main__":
    main()