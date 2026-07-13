import json

chunks_by_doc = {}
with open(r"C:\Users\dawar\Documents\MeezanBank_Internship\Projects\Proj6-Rag2\data\chunks.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        chunks_by_doc.setdefault(r["doc_id"], []).append(r)

target_doc = "_circulars_acfid-circular-letter-no-01-of-2025"
for c in chunks_by_doc[target_doc]:
    print(f"--- chunk {c['chunk_index']}/{c['total_chunks']} ({c['char_count']} chars) ---")
    print("START:", c["text"][:150])
    print("END:  ", c["text"][-150:])
    print()