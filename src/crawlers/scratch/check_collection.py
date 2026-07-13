import chromadb

client = chromadb.PersistentClient(path="data/vector_db")
collection = client.get_or_create_collection(name="sbp_circulars")

print(f"Total chunks in collection: {collection.count()}")