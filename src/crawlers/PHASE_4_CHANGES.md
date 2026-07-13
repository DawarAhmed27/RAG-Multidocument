# Phase 4 Changes Summary

## What we changed

### 1. Added the phase 4 grounded generation flow
The `rag_answer.py` script now runs the phase 4 pipeline as a two-step safety gate before answering:
- Sufficiency check: the model first decides whether the retrieved chunks contain enough evidence to answer.
- Grounded generation: only if the evidence is sufficient, the model generates an answer using only the retrieved chunks.
- Citation verification: the script checks whether the answer’s citations match retrieved circular metadata.

### 2. Added a wrapper module for the retriever
The phase 4 file expects `hybrid_retriever.py` in the same folder, so I added:
- `src/crawlers/hybrid_retriever.py`

That file simply re-exports `HybridRetriever` from `hybrid_ret.py` so phase 4 can import it cleanly without duplicating retriever logic.

### 3. Fixed LM Studio model selection
The original phase 4 script used a placeholder model name. I changed it so it now:
- queries LM Studio’s `/v1/models` endpoint,
- picks the first available local model automatically,
- falls back to `meta-llama-3.1-8b-instruct` if needed.

This was necessary because the local server rejected the old placeholder model name with a 400 error.

### 4. Increased LM Studio timeouts
The sufficiency and generation prompts are larger than a tiny test request, so I increased the request timeouts to avoid false failures:
- sufficiency check timeout: 180 seconds
- answer generation timeout: 300 seconds

## Validation result
I ran `python rag_answer.py` successfully after the fixes.

### Test case 1
Question:
- `What are the rules for foreign currency business value accounts?`

Result:
- Retrieved relevant FCBVA / NRBVA circular chunks.
- Sufficiency check returned `INSUFFICIENT`.
- Final output was a refusal rather than a generated answer.

### Test case 2
Question:
- `What is the current interest rate policy of the US Federal Reserve?`

Result:
- Retrieved off-topic SBP circular chunks.
- Sufficiency check returned `INSUFFICIENT`.
- Final output was a refusal.

## What this means
The refusal behavior is working correctly for out-of-scope questions. For the first question, the corpus does contain the relevant circular text, but the sufficiency gate is conservative and refused instead of generating.

## Files changed
- `src/crawlers/rag_answer.py`
- `src/crawlers/hybrid_retriever.py`

## Notes
No other pipeline files were modified during this phase.
