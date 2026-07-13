import json

chunks_by_doc = {}
with open(r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\chunks.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        chunks_by_doc.setdefault(r["doc_id"], []).append(r)

# only consider doc_ids that clearly look like real circular filenames
candidates = [
    doc_id for doc_id in chunks_by_doc
    if ("circular" in doc_id.lower() and "-no-" in doc_id.lower())
    and 4 <= len(chunks_by_doc[doc_id]) <= 6
]

print(f"Found {len(candidates)} candidates")
target_doc = candidates[0]
print(f"Inspecting: {target_doc}\n")

for c in chunks_by_doc[target_doc]:
    print(f"--- chunk {c['chunk_index']}/{c['total_chunks']} ({c['char_count']} chars) ---")
    print(c["text"][:300])
    print()