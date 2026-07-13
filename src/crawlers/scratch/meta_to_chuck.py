"""
Fix Contextual Prefixes — Add Missing Identity Metadata
---------------------------------------------------------
The LLM-generated prefixes (for multi-chunk documents) are topically good
but don't include circular number / department / date — meaning a chunk
retrieved standalone would have no way to be cited precisely. This does
NOT re-call the LLM; it just combines the deterministic identity line
(built from metadata already in each record) with the LLM blurb that's
already been generated, and rewrites text_with_context accordingly.

Usage:
    python fix_contextual_prefixes.py

Input / Output (in place, rewrites the same file):
    data/chunks_contextualized.jsonl
"""

import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

CHUNKS_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks_contextualized.jsonl")


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


def run():
    with open(CHUNKS_JSONL, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]

    fixed_count = 0
    for row in rows:
        if row.get("contextual_method") in ("llm", "deterministic_fallback"):
            identity_line = build_deterministic_prefix(row)
            llm_blurb = row["contextual_prefix"]
            combined = f"{identity_line} {llm_blurb}"
            row["contextual_prefix"] = combined
            row["text_with_context"] = f"{combined}\n\n{row['text']}"
            if row["contextual_method"] == "llm":
                row["contextual_method"] = "llm_plus_deterministic"
            fixed_count += 1

    with open(CHUNKS_JSONL, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Fixed {fixed_count} chunks (added identity metadata to LLM-generated prefixes)")
    print(f"Rewrote: {CHUNKS_JSONL}")


if __name__ == "__main__":
    run()