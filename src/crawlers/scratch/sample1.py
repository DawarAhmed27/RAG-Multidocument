from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

query = "Represent this sentence for searching relevant passages: public holiday"
query_embedding = model.encode(query, normalize_embeddings=True)

results = collection.query(
    query_embeddings=[query_embedding.tolist()],
    n_results=3,
)

for i, doc_id in enumerate(results["ids"][0]):
    print(f"\n{i+1}. {doc_id}")
    print("   Metadata:", results["metadatas"][0][i])
    print("   Text:", results["documents"][0][i][:150])