import json

target_doc = None
chunks_by_doc = {}
with open(r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\chunks.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        chunks_by_doc.setdefault(r["doc_id"], []).append(r)

# grab any doc that got split into, say, 4-6 chunks — a representative middle case
for doc_id, chunks in chunks_by_doc.items():
    if 4 <= len(chunks) <= 6:
        target_doc = doc_id
        break

for c in chunks_by_doc[target_doc]:
    print(f"--- chunk {c['chunk_index']}/{c['total_chunks']} ({c['char_count']} chars) ---")
    print(c["text"][:300])
    print()