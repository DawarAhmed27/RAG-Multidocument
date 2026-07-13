"""
Adaptive Chunker for SBP Corpus
--------------------------------
Calibrated against the real size distribution of data/docs_clean/:
  Count: 1007, Min: 87, Max: 15730, Avg: 1903 bytes

Most documents are short enough that a single chunk = the whole document.
Only the long tail needs real splitting. This avoids the common naive-RAG
mistake of blindly fixed-size-chunking every document regardless of length,
which would sever short regulatory notices mid-thought for no benefit.

Usage:
    python chunk_corpus.py

Input:
    data/docs_clean/*.txt

Output:
    data/chunks.jsonl
        one JSON object per line:
        {doc_id, chunk_id, chunk_index, total_chunks, text, char_count}
"""

import os
import json

# Resolve paths relative to this script's own location, not whatever folder
# you happen to run it from — avoids the "path not found" class of bug that's
# come up a couple of times in this project already.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Adjust the number of ".." segments if your folder layout differs. This
# assumes the script lives in src/crawlers/ and data/ is at the project root.
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))

DOCS_DIR = os.path.join(PROJECT_ROOT, "data", "docs_clean")
OUTPUT_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks.jsonl")

# Below this size, keep the whole document as one chunk — splitting a short
# circular in half loses more context than it gains.
SINGLE_CHUNK_MAX_CHARS = 1800

# For documents above that threshold, target this size per chunk...
CHUNK_TARGET_CHARS = 1200

# ...with this much text repeated at the start of the next chunk, so a clause
# split across a boundary still has surrounding context on both sides.
CHUNK_OVERLAP_CHARS = 150

# Flag anything this short for manual review — likely a broken/near-empty
# scrape rather than a real, usably short document.
SUSPICIOUSLY_SHORT_CHARS = 100


def split_into_paragraphs(text):
    # paragraphs separated by blank lines; fall back to single-newline split
    # if the document has no blank-line breaks at all
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paras) <= 1:
        paras = [p.strip() for p in text.split("\n") if p.strip()]
    return paras


def chunk_long_document(text):
    paragraphs = split_into_paragraphs(text)
    chunks = []
    current = ""

    for para in paragraphs:
        if current and len(current) + len(para) + 1 > CHUNK_TARGET_CHARS:
            chunks.append(current.strip())
            # start next chunk with overlap from the tail of the previous one,
            # snapped to a word boundary so we don't cut mid-word
            overlap_raw = current[-CHUNK_OVERLAP_CHARS:] if len(current) > CHUNK_OVERLAP_CHARS else current
            space_idx = overlap_raw.find(" ")
            overlap = overlap_raw[space_idx + 1:] if 0 <= space_idx < len(overlap_raw) - 1 else overlap_raw
            current = overlap + "\n" + para
        else:
            current = (current + "\n" + para) if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def chunk_document(doc_id, text):
    char_count = len(text)

    if char_count < SUSPICIOUSLY_SHORT_CHARS:
        print(f"  WARNING: {doc_id} is only {char_count} chars — check manually, may be broken")

    if char_count <= SINGLE_CHUNK_MAX_CHARS:
        chunk_texts = [text]
    else:
        chunk_texts = chunk_long_document(text)

    records = []
    total = len(chunk_texts)
    for i, chunk_text in enumerate(chunk_texts):
        records.append({
            "doc_id": doc_id,
            "chunk_id": f"{doc_id}__chunk{i}",
            "chunk_index": i,
            "total_chunks": total,
            "text": chunk_text,
            "char_count": len(chunk_text),
        })
    return records


def run():
    filenames = sorted(f for f in os.listdir(DOCS_DIR) if f.endswith(".txt"))
    print(f"Found {len(filenames)} cleaned documents")

    all_records = []
    multi_chunk_docs = 0

    for fname in filenames:
        doc_id = fname[:-4]
        path = os.path.join(DOCS_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        records = chunk_document(doc_id, text)
        if len(records) > 1:
            multi_chunk_docs += 1
        all_records.extend(records)

    os.makedirs(os.path.dirname(OUTPUT_JSONL), exist_ok=True)
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\nTotal chunks: {len(all_records)}")
    print(f"Documents split into multiple chunks: {multi_chunk_docs} / {len(filenames)}")
    print(f"Documents kept as a single chunk: {len(filenames) - multi_chunk_docs}")
    print(f"Output: {OUTPUT_JSONL}")


if __name__ == "__main__":
    run()