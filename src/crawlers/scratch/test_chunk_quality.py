import json

samples_llm = []
samples_det = []

with open("C:\\Users\\dawar\\Documents\\MeezanBank_Internship\\Projects\\Proj6-Rag2\\data\\chunks_contextualized.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r["contextual_method"] == "llm" and len(samples_llm) < 3:
            samples_llm.append(r)
        elif r["contextual_method"] == "deterministic" and len(samples_det) < 2:
            samples_det.append(r)
        if len(samples_llm) >= 3 and len(samples_det) >= 2:
            break

print("=== LLM-generated prefixes ===")
for r in samples_llm:
    print(f"\n{r['chunk_id']} (chunk {r['chunk_index']}/{r['total_chunks']})")
    print("PREFIX:", r["contextual_prefix"])

print("\n=== Deterministic prefixes ===")
for r in samples_det:
    print(f"\n{r['chunk_id']}")
    print("PREFIX:", r["contextual_prefix"])