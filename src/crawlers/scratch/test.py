"""
Universal SBP Corpus Cleaner (v2)
----------------------------------
Your data/docs/ folder now contains output from at least 3 different scraper
runs (BeautifulSoup+requests, Playwright, Crawlee+Playwright), each with
different boilerplate patterns:
  - old runs: duplicate-rendered body + "Accessibility Tools" footer
  - new runs: full site mega-menu captured by innerText()

Rather than writing per-scraper cleaners, this anchors on the ONE thing
that's consistent across every sample seen so far: real content starts right
after a "Home" -> "Circulars"/"Notifications" breadcrumb pair, and ends right
before a footer marker (USEFUL LINKS / Copyright / Accessibility Tools /
the duplicate-render marker).

Usage:
    python clean_corpus_v2.py

Input:
    data/docs/*.txt  (or .txt-with-no-extension files too, see NOTE below)

Output:
    data/docs_clean/*.txt
    data/cleaning_report.csv   -> per-file: found_start, found_end, before/after char counts
"""

import os
import re
import csv

DOCS_DIR = r'C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\docs'
CLEAN_DIR = r'C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\docs_clean'
REPORT_CSV = r'C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\cleaning_report.csv'

# End-of-content markers, in priority order — whichever appears FIRST in the
# text is where we cut. Covers both old-scraper and new-scraper footers.
END_MARKERS = [
    "Home\n—\nCirculars\n—",   # old scraper: duplicate re-render begins here
    "Accessibility Tools",      # old scraper: accessibility toolbar
    "USEFUL LINKS",             # new scraper: footer nav begins here
    "Copyright ©",              # fallback footer marker
]

BREADCRUMB_PATTERN = re.compile(r"^Home$\n^(Circulars|Notifications)$", re.MULTILINE)


def find_content_start(text):
    """Return index right after the Home / Circulars|Notifications breadcrumb pair,
    or None if not found."""
    match = BREADCRUMB_PATTERN.search(text)
    if match:
        return match.end()
    return None


def find_content_end(text, start_idx):
    end_idx = len(text)
    for marker in END_MARKERS:
        idx = text.find(marker, start_idx)
        if idx != -1:
            end_idx = min(end_idx, idx)
    return end_idx


def clean_text(text):
    start_idx = find_content_start(text)
    if start_idx is None:
        # couldn't find the breadcrumb anchor — return None to flag for manual review
        return None, "start_marker_not_found"

    end_idx = find_content_end(text, start_idx)
    body = text[start_idx:end_idx].strip()

    lines = [l.strip() for l in body.split("\n") if l.strip()]
    body = "\n".join(lines)

    if len(body) < 50:
        return body, "suspiciously_short_after_clean"

    return body, "ok"


def run():
    os.makedirs(CLEAN_DIR, exist_ok=True)
    rows = []

    filenames = sorted(os.listdir(DOCS_DIR))
    print(f"Found {len(filenames)} files in {DOCS_DIR}")

    for fname in filenames:
        path = os.path.join(DOCS_DIR, fname)
        if not os.path.isfile(path):
            continue

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
        except Exception as e:
            rows.append({"filename": fname, "status": f"read_error: {e}",
                         "before_chars": 0, "after_chars": 0})
            continue

        before_chars = len(raw_text)
        cleaned, status = clean_text(raw_text)
        after_chars = len(cleaned) if cleaned else 0

        if cleaned is not None and status == "ok":
            out_name = fname if fname.endswith(".txt") else fname + ".txt"
            with open(os.path.join(CLEAN_DIR, out_name), "w", encoding="utf-8") as f:
                f.write(cleaned)

        rows.append({
            "filename": fname, "status": status,
            "before_chars": before_chars, "after_chars": after_chars,
        })

    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "status", "before_chars", "after_chars"])
        writer.writeheader()
        writer.writerows(rows)

    ok_count = sum(1 for r in rows if r["status"] == "ok")
    print(f"\nCleaned successfully: {ok_count} / {len(rows)}")
    print("Status breakdown:")
    from collections import Counter
    print(Counter(r["status"] for r in rows))
    print(f"\nFull report: {REPORT_CSV}")
    print(f"Clean files: {CLEAN_DIR}/")


if __name__ == "__main__":
    run()