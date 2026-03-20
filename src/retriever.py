import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="regulations")

def retrieve(query, n_results=5):
    embedding = model.encode(query).tolist()
    results = collection.query(
        query_embeddings=[embedding],
        n_results=n_results
    )
    
    chunks = results["documents"][0]
    sources = [m["source"] for m in results["metadatas"][0]]
    
    return list(zip(chunks, sources))
