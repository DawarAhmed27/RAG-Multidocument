import csv
import os

PROJECT_ROOT = r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2"

with open(os.path.join(PROJECT_ROOT, "data", "doc_metadata.csv"), encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

review = [r["doc_id"] for r in rows if r["status"] == "needs_manual_review"]
partial = [r["doc_id"] for r in rows if r["status"] == "partial_fallback"]

print(f"needs_manual_review: {len(review)}")
print(review[:10])
print(f"\npartial_fallback: {len(partial)}")
print(partial[:10])

for doc_id in (review[:5] + partial[:5]):
    print(f"\n=== {doc_id} ===")
    with open(os.path.join(PROJECT_ROOT, "data", "docs_clean", f"{doc_id}.txt"), encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    print(lines[:5])