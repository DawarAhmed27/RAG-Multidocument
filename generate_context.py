"""
Contextual Chunk Prefix Generator
-----------------------------------
Implements Anthropic's "Contextual Retrieval" idea, but only where it earns
its keep:

  - Single-chunk documents (692 of your 895): the chunk IS the whole
    document, so its own header already contains circular number/title/date.
    A generated blurb would just restate that. These get a fast, free,
    deterministic prefix built straight from extracted metadata.

  - Multi-chunk documents (203 of your 895, 779 chunks total): chunks after
    the first one genuinely lose their identity when retrieved standalone
    (chunk 3 of 6 has no idea what document it's from). These get a real
    LLM-generated blurb via your local LM Studio server, using the FULL
    source document as context, following the chunk situates-in-document
    pattern.

This roughly halves your LLM calls (779 instead of 1471) versus running
every chunk through the model regardless of whether it needs it.

Requirements:
    - LM Studio running locally with a model loaded and the local server
      started (usually http://localhost:1234)
    - pip install requests

Usage:
    python generate_contextual_prefixes.py

Input:
    data/chunks_with_metadata.jsonl
    data/docs_clean/*.txt   (for full-document context on multi-chunk docs)

Output:
    data/chunks_contextualized.jsonl
        adds: contextual_prefix, text_with_context, contextual_method
"""

import os
import json
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))  # adjust if your layout differs

CHUNKS_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks_with_metadata.jsonl")
DOCS_DIR = os.path.join(PROJECT_ROOT, "data", "docs_clean")
OUTPUT_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks_contextualized.jsonl")

LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"
LM_STUDIO_MODEL = "local-model"  # LM Studio ignores this if only one model is loaded; set to your loaded model's name if needed

# Cap how much of the source document gets sent as context per LLM call —
# keeps prompts fast on local inference. Generous given your average
# document is ~1900 bytes; only affects the handful of longer documents.
MAX_DOC_CONTEXT_CHARS = 6000

CONTEXTUALIZE_PROMPT_TEMPLATE = """<document>
{doc_text}
</document>

Here is a specific excerpt (chunk {chunk_index} of {total_chunks}) from the document above:

<chunk>
{chunk_text}
</chunk>

Write a short, 1-2 sentence context statement to situate this specific chunk within the overall document, to improve search retrieval of this chunk. Focus on what makes this particular excerpt distinct from other parts of the document (e.g. which clause, section, or topic it covers). Answer with ONLY the context statement, nothing else."""


def build_deterministic_prefix(meta):
    parts = []
    if meta.get("circular_number"):
        parts.append(meta["circular_number"])
    elif meta.get("department"):
        parts.append(f"{meta['department']} document")
    if meta.get("date"):
        parts.append(f"dated {meta['date']}")
    if meta.get("title"):
        parts.append(f"titled '{meta['title']}'")
    if not parts:
        return "SBP regulatory document."
    return "This excerpt is from " + ", ".join(parts) + "."


def call_lm_studio(prompt, timeout=60):
    payload = {
        "model": LM_STUDIO_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 100,
    }
    resp = requests.post(LM_STUDIO_URL, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def check_lm_studio_available():
    try:
        requests.get("http://localhost:1234/v1/models", timeout=5)
        return True
    except requests.RequestException:
        return False


def load_already_processed():
    if not os.path.exists(OUTPUT_JSONL):
        return set()
    done = set()
    with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
                done.add(r["chunk_id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def run():
    if not check_lm_studio_available():
        print("ERROR: LM Studio server not reachable at http://localhost:1234")
        print("Start the local server in LM Studio (Developer tab) before running this.")
        return

    already_done = load_already_processed()
    print(f"Resuming: {len(already_done)} chunks already processed, will be skipped.")

    doc_text_cache = {}

    with open(CHUNKS_JSONL, "r", encoding="utf-8") as f:
        all_chunks = [json.loads(line) for line in f]

    print(f"Total chunks: {len(all_chunks)}")

    single_chunk_count = 0
    llm_chunk_count = 0
    failed_count = 0

    with open(OUTPUT_JSONL, "a", encoding="utf-8") as outfile:
        for chunk in all_chunks:
            if chunk["chunk_id"] in already_done:
                continue

            if chunk["total_chunks"] == 1:
                prefix = build_deterministic_prefix(chunk)
                chunk["contextual_prefix"] = prefix
                chunk["text_with_context"] = f"{prefix}\n\n{chunk['text']}"
                chunk["contextual_method"] = "deterministic"
                single_chunk_count += 1
            else:
                doc_id = chunk["doc_id"]
                if doc_id not in doc_text_cache:
                    doc_path = os.path.join(DOCS_DIR, f"{doc_id}.txt")
                    try:
                        with open(doc_path, "r", encoding="utf-8") as f:
                            doc_text_cache[doc_id] = f.read()[:MAX_DOC_CONTEXT_CHARS]
                    except FileNotFoundError:
                        doc_text_cache[doc_id] = chunk["text"]  # fallback: use chunk itself

                prompt = CONTEXTUALIZE_PROMPT_TEMPLATE.format(
                    doc_text=doc_text_cache[doc_id],
                    chunk_index=chunk["chunk_index"],
                    total_chunks=chunk["total_chunks"],
                    chunk_text=chunk["text"],
                )

                try:
                    llm_prefix = call_lm_studio(prompt)
                    chunk["contextual_prefix"] = llm_prefix
                    chunk["text_with_context"] = f"{llm_prefix}\n\n{chunk['text']}"
                    chunk["contextual_method"] = "llm"
                    llm_chunk_count += 1
                except Exception as e:
                    print(f"  FAILED on {chunk['chunk_id']}: {e}")
                    # fall back to deterministic so nothing is left un-embeddable
                    prefix = build_deterministic_prefix(chunk)
                    chunk["contextual_prefix"] = prefix
                    chunk["text_with_context"] = f"{prefix}\n\n{chunk['text']}"
                    chunk["contextual_method"] = "deterministic_fallback"
                    failed_count += 1

            outfile.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            outfile.flush()

            processed = single_chunk_count + llm_chunk_count + failed_count
            if processed % 50 == 0:
                print(f"  ...{processed} chunks processed so far")

    print(f"\nDone.")
    print(f"Deterministic prefixes: {single_chunk_count}")
    print(f"LLM-generated prefixes: {llm_chunk_count}")
    print(f"LLM failures (fell back to deterministic): {failed_count}")
    print(f"Output: {OUTPUT_JSONL}")


if __name__ == "__main__":
    run()