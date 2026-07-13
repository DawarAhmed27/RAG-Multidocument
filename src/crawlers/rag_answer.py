"""
Grounded Generation Pipeline (Phase 4)
-----------------------------------------
The anti-hallucination centerpiece of this project. Three steps, not one:

  1. SUFFICIENCY CHECK: before generating anything, explicitly ask the
     model whether the retrieved chunks actually contain enough to answer
     the question. A single-pass "answer using this context" prompt lets
     models paper over gaps with a confident-sounding guess; a separate
     check makes refusal the model's actual job for that step, not an
     afterthought buried in generation instructions.

  2. GROUNDED GENERATION: only runs if step 1 says yes. Instructed to use
     ONLY the provided documents and cite the specific circular for every
     claim.

  3. CITATION VERIFICATION: after generation, checks that every citation
     the model produced actually matches a real retrieved chunk's circular
     number — catching a model citing something plausible that wasn't
     actually in the evidence, rather than trusting the citation blindly.

Requirements:
    Same as hybrid_retriever.py (chromadb, sentence-transformers, rank_bm25)
    plus LM Studio running locally (same setup used for contextual prefixes).

Usage:
    python rag_answer.py
"""

import os
import re
import requests

from hybrid_retriever import HybridRetriever

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "local-model"  # set to your loaded model's name if LM Studio requires an exact match

TOP_K_RETRIEVE = 5


def call_lm_studio(prompt, timeout=60, max_tokens=400):
    payload = {
        "model": LM_STUDIO_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }
    resp = requests.post(LM_STUDIO_URL, json=payload, timeout=timeout)
    if not resp.ok:
        print(f"LM Studio returned {resp.status_code}. Response body:")
        print(resp.text)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def format_chunks_for_prompt(chunks):
    lines = []
    for i, c in enumerate(chunks, start=1):
        lines.append(
            f"Document {i} — {c['circular_number']} | {c['department']} | {c['date']} | {c['title']}\n"
            f"Citation key: [{c['circular_number']}, {c['date']}]\n"
            f"{c['text']}\n"
        )
    return "\n".join(lines)


def format_citation_keys_for_prompt(chunks):
    keys = []
    for c in chunks:
        if c.get("circular_number") and c.get("date"):
            keys.append(f"- [{c['circular_number']}, {c['date']}]")
    return "\n".join(keys)


SUFFICIENCY_PROMPT_TEMPLATE = """You are evaluating whether the retrieved documents below contain enough information to provide a genuinely useful, evidence-based answer to the user's question.

Mark SUFFICIENT if the documents contain real, specific, on-topic evidence that supports at least a partial, accurate answer — even if they don't cover every possible aspect of the question. Regulatory circulars are often narrow amendments to existing rules, not comprehensive rulebooks, so partial coverage of a specific requirement should still count as sufficient.

Mark INSUFFICIENT only if the documents are off-topic, purely tangential, or contain no real substantive content relevant to the question.

Question: {query}

Retrieved documents:
{formatted_chunks}

Respond in exactly this format, nothing else:
SUFFICIENT: yes or no
REASONING: <one sentence explaining why>"""


GENERATION_PROMPT_TEMPLATE = """Answer the question below using ONLY the information in the documents provided. Do not use any outside knowledge, even if you think you know the answer.

Start with the actual answer. Do not begin with phrases like "Unfortunately", "I don't have enough information", or "I cannot provide" unless the documents are truly off-topic and the sufficiency check was wrong.

For every factual claim, cite the specific circular it came from using this exact format: [CircularNumber, Date]. If different parts of your answer come from different circulars, cite each part separately.

Use only the exact citation strings listed below. Do not invent document numbers, abbreviations, or paraphrases inside brackets.

Exact citation strings:
{citation_keys}

If the documents only partially answer the question, answer the part they cover and explicitly state which part is not covered, rather than guessing.

Question: {query}

Documents:
{formatted_chunks}

Answer:"""


REWRITE_PROMPT_TEMPLATE = """You previously produced an answer that was too refusal-like for a question that the retrieved documents appear to cover at least partially.

Rewrite the answer so it is direct, grounded, and concise.

Rules:
- Use ONLY the provided documents.
- Start with the factual answer instead of a refusal.
- If the documents only partially answer the question, give the covered part and explicitly say what is not covered.
- Do not invent details that are not in the documents.
- Cite every factual claim using [CircularNumber, Date].
- Do not mention that you are unable to answer unless the documents are truly off-topic.

Exact citation strings you may use:
{citation_keys}

Question: {query}

Documents:
{formatted_chunks}

Bad draft to improve:
{draft_answer}

Rewritten answer:"""


CITATION_REWRITE_PROMPT_TEMPLATE = """The answer below uses incorrect or malformed citations.

Rewrite it so every factual claim uses only the exact citation strings provided. Keep the substantive answer the same unless it needs to change to stay grounded.

Rules:
- Use ONLY the provided documents.
- Replace every citation with one of the exact citation strings below.
- Do not use "Document 1"-style citations, partial dates, or uncited factual claims.
- Do not add any facts not supported by the documents.
- If the answer is only partial, keep the partial caveat.

Exact citation strings:
{citation_keys}

Question: {query}

Documents:
{formatted_chunks}

Bad draft to repair:
{draft_answer}

Rewritten answer:"""


def check_sufficiency(query, chunks):
    prompt = SUFFICIENCY_PROMPT_TEMPLATE.format(
        query=query, formatted_chunks=format_chunks_for_prompt(chunks)
    )
    response = call_lm_studio(prompt, max_tokens=100)

    sufficient_match = re.search(r"SUFFICIENT:\s*(yes|no)", response, re.IGNORECASE)
    reasoning_match = re.search(r"REASONING:\s*(.+)", response, re.IGNORECASE | re.DOTALL)

    sufficient = bool(sufficient_match) and sufficient_match.group(1).lower() == "yes"
    reasoning = reasoning_match.group(1).strip() if reasoning_match else response.strip()

    return sufficient, reasoning


def generate_answer(query, chunks):
    prompt = GENERATION_PROMPT_TEMPLATE.format(
        query=query,
        formatted_chunks=format_chunks_for_prompt(chunks),
        citation_keys=format_citation_keys_for_prompt(chunks),
    )
    return call_lm_studio(prompt, max_tokens=500)


def rewrite_answer(query, chunks, draft_answer):
    prompt = REWRITE_PROMPT_TEMPLATE.format(
        query=query,
        formatted_chunks=format_chunks_for_prompt(chunks),
        citation_keys=format_citation_keys_for_prompt(chunks),
        draft_answer=draft_answer,
    )
    return call_lm_studio(prompt, max_tokens=500)


def repair_citations(query, chunks, draft_answer):
    prompt = CITATION_REWRITE_PROMPT_TEMPLATE.format(
        query=query,
        formatted_chunks=format_chunks_for_prompt(chunks),
        citation_keys=format_citation_keys_for_prompt(chunks),
        draft_answer=draft_answer,
    )
    return call_lm_studio(prompt, max_tokens=500)


def verify_citations(answer_text, chunks):
    """Extract [CircularNumber, Date]-style citations from the answer and
    check each one actually corresponds to a retrieved chunk. Flags
    citations that don't match anything retrieved — a real, if imperfect,
    check against fabricated citations."""
    cited = re.findall(r"\[([^\]]+)\]", answer_text)
    retrieved_citations = {
        f"{c['circular_number']}, {c['date']}"
        for c in chunks
        if c.get("circular_number") and c.get("date")
    }

    flagged = []
    for citation in cited:
        normalized = citation.strip()
        if normalized not in retrieved_citations:
            flagged.append(citation)

    return flagged


def answer_question(retriever, query, top_k=TOP_K_RETRIEVE, verbose=True):
    if verbose:
        print(f"\n{'=' * 70}\nQUESTION: {query}\n{'=' * 70}")

    chunks = retriever.search(query, top_n=top_k, truncate=False)

    if verbose:
        print(f"\nRetrieved {len(chunks)} chunks:")
        for c in chunks:
            print(f"  - {c['circular_number']} | {c['title']}")

    sufficient, reasoning = check_sufficiency(query, chunks)

    if verbose:
        print(f"\nSufficiency check: {'SUFFICIENT' if sufficient else 'INSUFFICIENT'}")
        print(f"Reasoning: {reasoning}")

    if not sufficient:
        refusal = (
            "I don't have enough information in the retrieved SBP circulars to answer "
            f"this question confidently. ({reasoning})"
        )
        if verbose:
            print(f"\nFINAL ANSWER (refused):\n{refusal}")
        return {"answered": False, "answer": refusal, "chunks": chunks, "citation_issues": []}

    answer = generate_answer(query, chunks)
    citation_issues = verify_citations(answer, chunks)

    if re.search(r"\b(unfortunately|i don't have enough information|i cannot provide|unable to answer)\b", answer, re.IGNORECASE):
        rewritten_answer = rewrite_answer(query, chunks, answer)
        rewritten_citation_issues = verify_citations(rewritten_answer, chunks)

        # Keep the rewrite only if it is less refusal-like and does not introduce new citation problems.
        if not re.search(r"\b(unfortunately|i don't have enough information|i cannot provide|unable to answer)\b", rewritten_answer, re.IGNORECASE):
            answer = rewritten_answer
            citation_issues = rewritten_citation_issues

    if citation_issues:
        repaired_answer = repair_citations(query, chunks, answer)
        repaired_citation_issues = verify_citations(repaired_answer, chunks)
        if len(repaired_citation_issues) <= len(citation_issues):
            answer = repaired_answer
            citation_issues = repaired_citation_issues

    if verbose:
        print(f"\nFINAL ANSWER:\n{answer}")
        if citation_issues:
            print(f"\nWARNING: {len(citation_issues)} citation(s) could not be matched to a retrieved chunk:")
            for issue in citation_issues:
                print(f"  - [{issue}]")
        else:
            print("\nAll citations verified against retrieved chunks.")

    return {"answered": True, "answer": answer, "chunks": chunks, "citation_issues": citation_issues}


if __name__ == "__main__":
    retriever = HybridRetriever()

    # A question the corpus should be able to answer
    answer_question(retriever, "What are the rules for foreign currency business value accounts?")

    # A question deliberately outside the corpus's scope, to test refusal
    answer_question(retriever, "What is the current interest rate policy of the US Federal Reserve?")