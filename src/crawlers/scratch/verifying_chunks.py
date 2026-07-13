import json

with open("C:\\Users\\dawar\\Documents\\MeezanBank_Internship\\Projects\\Proj6-Rag2\\data\\chunks_contextualized.jsonl", encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r["chunk_id"] == "_circulars_acd-cir-letter-no2-of-2002__chunk1":
            print(r["contextual_prefix"])
            break