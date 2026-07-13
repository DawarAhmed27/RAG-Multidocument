"""
Listing-Page Detector
----------------------
Finds documents in data/docs_clean/ that are actually the site's paginated
search/listing pages (e.g. "Filter By Year", "1 2 3 ... 133 >"), scraped as
if they were real circulars. These pollute the corpus with content that
looks topically relevant (full of real department names/dates) but answers
nothing — a direct hallucination risk if ever retrieved.

Usage:
    python find_listing_pages.py

Output:
    Prints matching doc_ids and moves them to data/docs_clean_quarantine/
    (does NOT delete — quarantine so you can double-check before permanent
    removal).
"""

import os
import re
import shutil

DOCS_DIR = r'C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\docs_clean'
QUARANTINE_DIR = r'C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\docs_clean_quarantine'      

# Any of these strongly indicate a listing/search page, not a real document
LISTING_PAGE_MARKERS = [
    "Filter By Year",
    "Filter By Department",
    "Filter By Circular Type",
    "Filter By Category",
]

# Pagination footer pattern like "1 2 3 ... 133 >" or the count line "3990 circulars."
PAGINATION_PATTERN = re.compile(r"\b\d{2,5}\s+circulars\.", re.IGNORECASE)


def is_listing_page(text):
    if any(marker in text for marker in LISTING_PAGE_MARKERS):
        return True
    if PAGINATION_PATTERN.search(text):
        return True
    return False


def run():
    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    filenames = sorted(f for f in os.listdir(DOCS_DIR) if f.endswith(".txt"))

    flagged = []
    for fname in filenames:
        path = os.path.join(DOCS_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if is_listing_page(text):
            flagged.append(fname)
            shutil.move(path, os.path.join(QUARANTINE_DIR, fname))

    print(f"Scanned {len(filenames)} documents")
    print(f"Flagged and quarantined: {len(flagged)}")
    for f in flagged:
        print(f"  {f}")
    print(f"\nRemaining clean documents: {len(filenames) - len(flagged)}")
    print(f"Quarantined files moved to: {QUARANTINE_DIR}/ (review before deleting permanently)")


if __name__ == "__main__":
    run()