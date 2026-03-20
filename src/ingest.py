import pdfplumber
import chromadb
from sentence_transformers import SentenceTransformer
import os

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Initialize ChromaDB
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="regulations")

def chunk_text(text, chunk_size=500, overlap=50):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def ingest_pdf(pdf_path):
    filename = os.path.basename(pdf_path)
    print(f"Processing: {filename}")
    
    with pdfplumber.open(pdf_path) as pdf:
        full_text = ""
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                full_text += text + " "
    
    chunks = chunk_text(full_text)
    
    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk).tolist()
        collection.add(
            documents=[chunk],
            embeddings=[embedding],
            ids=[f"{filename}_chunk_{i}"],
            metadatas=[{"source": filename}]
        )
    
    print(f"✅ Done: {filename} — {len(chunks)} chunks stored")

def ingest_all(folder_path="./regulations"):
    files = [f for f in os.listdir(folder_path) if f.endswith(".pdf")]
    for file in files:
        ingest_pdf(os.path.join(folder_path, file))
    print("\n✅ All PDFs ingested successfully.")

if __name__ == "__main__":
    ingest_all()
