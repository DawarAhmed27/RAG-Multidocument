"""
Metadata Extractor
-------------------
Extracts (department, circular_number, year, date, title, doc_type) from
each cleaned document, then joins that metadata onto every chunk belonging
to that document.

Handles the two header patterns confirmed against real samples in this
project:
  Type A ("circular"):     "BPRD Circular Letter No. 02 of 2025"
                            followed by title line, then date line
  Type B ("notification"): "No. BPRD (DBD) /4305/2025"
                            followed by "NOTIFICATION", then date line

Falls back to extracting department from the filename slug if the body
text doesn't match either pattern (corpus mixes several scraper generations
with different filename conventions — both hyphen and underscore separators
are handled).

Anything that can't be confidently parsed is flagged in the report rather
than silently guessed — same approach used throughout this project's
cleaning scripts.

Usage:
    python extract_metadata.py

Input:
    data/docs_clean/*.txt
    data/chunks.jsonl

Output:
    data/doc_metadata.csv          -> one row per document
    data/chunks_with_metadata.jsonl -> chunks.jsonl enriched with metadata
"""

import os
import re
import csv
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))  # adjust if your layout differs

DOCS_DIR = os.path.join(PROJECT_ROOT, "data", "docs_clean")
CHUNKS_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks.jsonl")
DOC_METADATA_CSV = os.path.join(PROJECT_ROOT, "data", "doc_metadata.csv")
ENRICHED_CHUNKS_JSONL = os.path.join(PROJECT_ROOT, "data", "chunks_with_metadata.jsonl")

DATE_PATTERN = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},?\s+\d{4}\b"
)

# Type A: "ACD Circular No. 01" (older docs, year only in date line)
#      or "BPRD Circular Letter No. 02 of 2025" (newer docs, year inline)
#      or "ACD Cir Letter No.1" (older abbreviation "Cir" instead of "Circular")
# Department codes can contain hyphens (e.g. "BC-CPD").
CIRCULAR_HEADER_RE = re.compile(
    r"^([A-Za-z0-9&\-]+)\s+Cir(?:cular)?(?:\s+Letter)?\s+No\.?\s*([\w\-/]+?)"
    r"(?:\s+of\s+(\d{4}))?\s*$",
    re.IGNORECASE,
)

# Type B: "No. BPRD (DBD) /4305/2025" or "No. BPRD (LD-01)/602/2025/947802"
NOTIFICATION_HEADER_RE = re.compile(
    r"^No\.\s*([A-Za-z0-9&]+)\s*(?:\(([^)]+)\))?\s*/\s*([\w\-]+)\s*/\s*(\d{4})",
    re.IGNORECASE,
)

# Fallback: pull department code out of the filename slug itself.
# Matches e.g. "circulars_acfid-circular-letter-no-01-of-2025"
#           or "notifications_no-bprd-dbd-4305-2025"
#           or "circulars_bprd-01-letter-of-2000" (no "circular" word at all)
FILENAME_CIRCULAR_RE = re.compile(r"circulars?_([a-z0-9&]+)-circular", re.IGNORECASE)
FILENAME_NOTIFICATION_RE = re.compile(r"notifications?_no-([a-z0-9&]+)", re.IGNORECASE)
FILENAME_GENERIC_RE = re.compile(r"circulars?_([a-z0-9]+)", re.IGNORECASE)


def extract_from_body(lines):
    """Try both header patterns against the first line of cleaned body text."""
    if not lines:
        return None

    first_line = lines[0].strip()

    m = CIRCULAR_HEADER_RE.match(first_line)
    if m:
        department, number, inline_year = m.group(1).upper(), m.group(2), m.group(3)
        title = lines[1].strip() if len(lines) > 1 else ""
        date = ""
        year = inline_year or ""
        for line in lines[1:6]:
            date_match = DATE_PATTERN.search(line)
            if date_match:
                date = date_match.group(0)
                if not year:
                    year_match = re.search(r"\d{4}", date)
                    if year_match:
                        year = year_match.group(0)
                break
        circular_number = f"{department} Circular No. {number}" + (f" of {year}" if year else "")
        return {
            "department": department,
            "circular_number": circular_number,
            "year": year,
            "date": date,
            "title": title,
            "doc_type": "circular",
        }

    m = NOTIFICATION_HEADER_RE.match(first_line)
    if m:
        department, sub_code, number, year = m.group(1).upper(), m.group(2) or "", m.group(3), m.group(4)
        date = ""
        for line in lines[1:6]:
            date_match = DATE_PATTERN.search(line)
            if date_match:
                date = date_match.group(0)
                break
        ref = f"No. {department}" + (f" ({sub_code})" if sub_code else "") + f"/{number}/{year}"
        return {
            "department": department,
            "circular_number": ref,
            "year": year,
            "date": date,
            "title": "Notification",
            "doc_type": "notification",
        }

    return None


def extract_from_filename(doc_id):
    m = FILENAME_CIRCULAR_RE.search(doc_id)
    if m:
        return m.group(1).upper()
    m = FILENAME_NOTIFICATION_RE.search(doc_id)
    if m:
        return m.group(1).upper()
    # last resort: just take the leading alphanumeric token — catches slugs
    # like "bprd-01-letter-of-2000" or "bid-1-of-2001" that never contain
    # the word "circular" at all. May be incomplete for hyphenated codes
    # (e.g. only grabs "bc" from "bc-cpd-..."), which is why this tier stays
    # a fallback rather than counting as a confident "ok" match.
    m = FILENAME_GENERIC_RE.search(doc_id)
    if m:
        return m.group(1).upper()
    return None


def extract_metadata(doc_id, text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    result = extract_from_body(lines)

    if result:
        result["doc_id"] = doc_id
        result["status"] = "ok"
        return result

    # fallback: at least get department from the filename, flag the rest
    dept_fallback = extract_from_filename(doc_id)
    date = ""
    for line in lines[:8]:
        date_match = DATE_PATTERN.search(line)
        if date_match:
            date = date_match.group(0)
            break

    return {
        "doc_id": doc_id,
        "department": dept_fallback or "",
        "circular_number": "",
        "year": "",
        "date": date,
        "title": lines[0] if lines else "",
        "doc_type": "unknown",
        "status": "needs_manual_review" if not dept_fallback else "partial_fallback",
    }


def run():
    filenames = sorted(f for f in os.listdir(DOCS_DIR) if f.endswith(".txt"))
    print(f"Found {len(filenames)} documents")

    doc_metadata = {}
    for fname in filenames:
        doc_id = fname[:-4]
        with open(os.path.join(DOCS_DIR, fname), "r", encoding="utf-8") as f:
            text = f.read()
        doc_metadata[doc_id] = extract_metadata(doc_id, text)

    fieldnames = ["doc_id", "department", "circular_number", "year", "date", "title", "doc_type", "status"]
    with open(DOC_METADATA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(doc_metadata.values())

    from collections import Counter
    status_counts = Counter(m["status"] for m in doc_metadata.values())
    print("\nExtraction status breakdown:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")

    # join onto chunks
    if os.path.exists(CHUNKS_JSONL):
        enriched_count = 0
        with open(CHUNKS_JSONL, "r", encoding="utf-8") as infile, \
             open(ENRICHED_CHUNKS_JSONL, "w", encoding="utf-8") as outfile:
            for line in infile:
                chunk = json.loads(line)
                meta = doc_metadata.get(chunk["doc_id"], {})
                chunk["department"] = meta.get("department", "")
                chunk["circular_number"] = meta.get("circular_number", "")
                chunk["date"] = meta.get("date", "")
                chunk["title"] = meta.get("title", "")
                chunk["doc_type"] = meta.get("doc_type", "unknown")
                outfile.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                enriched_count += 1
        print(f"\nEnriched {enriched_count} chunks -> {ENRICHED_CHUNKS_JSONL}")
    else:
        print(f"\nNOTE: {CHUNKS_JSONL} not found, skipped chunk enrichment step")

    print(f"Doc-level metadata -> {DOC_METADATA_CSV}")


if __name__ == "__main__":
    run()