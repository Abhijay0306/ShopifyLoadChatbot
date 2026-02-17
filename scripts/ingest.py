import os
import shutil
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import PyPDFLoader
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except ImportError:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_core.documents import Document

# Configuration
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data"))
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend/chroma_db"))

def ingest_pdfs():
    print(f"Checking for PDFs in {DATA_DIR}...")
    
    if not os.path.exists(DATA_DIR):
        print(f"Data directory {DATA_DIR} does not exist.")
        return

    pdf_files = [f for f in os.listdir(DATA_DIR) if f.lower().endswith('.pdf')]
    if not pdf_files:
        print("No PDF files found.")
        return
    
    print(f"Found {len(pdf_files)} PDFs. Starting ingestion...")

    all_docs = []
    
    for filename in pdf_files:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            loader = PyPDFLoader(filepath)
            docs = loader.load()
            
            # Enhance metadata
            for doc in docs:
                doc.metadata['source_file'] = filename
                # infer category from filename if possible, or default to "General"
                doc.metadata['category'] = "Technical Data Sheet" 
                
            all_docs.extend(docs)
            print(f"Processed {filename} - {len(docs)} pages")
        except Exception as e:
            print(f"Error processing {filename}: {e}")

    # Chunking Strategy
    # Using a smaller chunk size to stay within context limits and improve retrieval precision
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    
    splits = text_splitter.split_documents(all_docs)
    print(f"Total chunks created: {len(splits)}")

    # Vector Database
    print("Generating embeddings and indexing (this may take a while)...")
    
    # Initialize Embedding Model (Free, Local)
    embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # clean up old db if exists to avoid duplicates during re-runs
    # Qdrant stores data in a different structure, so we might want to just let it handle it or clear it.
    # For local Qdrant, we can just delete the directory.
    if os.path.exists(DB_DIR):
        try:
            shutil.rmtree(DB_DIR)
        except OSError as e:
            print(f"Warning: Could not clear existing DB directory: {e}")

    # Create Qdrant DB
    # Local mode with on-disk storage
    from langchain_qdrant import QdrantVectorStore
    
    vector_db = QdrantVectorStore.from_documents(
        documents=splits,
        embedding=embedding_function,
        path=DB_DIR,
        collection_name="shopify_rag",
    )
    
    print(f"Ingestion complete! Vector DB saved to {DB_DIR}")

if __name__ == "__main__":
    ingest_pdfs()
