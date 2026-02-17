from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
import requests

load_dotenv(override=True)

app = FastAPI()

# Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
print(f"Loaded DEEPSEEK_API_KEY (first 6 chars): {DEEPSEEK_API_KEY[:6]}...")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
# Using a relative path that works both locally and potentially in container
DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_db"))

# Initialize Retrieval components
# Warning: Loading this on Vercel might be heavy.
print("Loading embeddings model...")
try:
    embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # Check if DB exists
    if os.path.exists(DB_DIR):
        print(f"Loading Vector DB from {DB_DIR}")
        vector_db = QdrantVectorStore.from_existing_collection(
            embedding=embedding_function,
            path=DB_DIR,
            collection_name="shopify_rag"
        )
    else:
        print("Warning: Vector DB not found. Retrieval will fail.")
        vector_db = None
except Exception as e:
    print(f"Error loading retrieval components: {e}")
    vector_db = None

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    answer: str
    sources: list

@app.get("/")
def read_root():
    return {"message": "Shopify RAG Backend is running"}

@app.post("/ask", response_model=QueryResponse)
def ask_question(request: QueryRequest):
    query = request.query
    
    if not vector_db:
        raise HTTPException(status_code=503, detail="Vector DB not initialized")
    
    # 1. Retrieve relevant chunks
    try:
        # Retrieve top 3 relevant chunks
        results = vector_db.similarity_search(query, k=3)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")
        
    if not results:
        return QueryResponse(answer="No relevant information found in the technical data sheets.", sources=[])
    
    # 2. Format Context
    context_text = "\n\n".join([f"Source: {doc.metadata.get('source_file', 'Unknown')}\n{doc.page_content}" for doc in results])
    
    # 3. Call DeepSeek API
    if not DEEPSEEK_API_KEY:
         return QueryResponse(
             answer="DeepSeek API Key is missing. Please set DEEPSEEK_API_KEY in .env. (Mock Response: " + context_text[:100] + "...)", 
             sources=[doc.metadata.get('source_file') for doc in results]
         )

    system_prompt = """You are a helpful technical assistant for Abacus Digital. 
    your expertise lies in high-performance RAG (Retrieval-Augmented Generation) systems. 
    Connection to Shopify Storefront: You are integrated into a Shopify store.
    
    Instructions:
    - Answer the user's question based ONLY on the provided context.
    - If the context does not contain the answer, say "I couldn't find that information in the data sheets."
    - Be clinical, non-verbose, and precise.
    - Reference specific products or specs if mentioned in the context.
    """
    
    user_prompt = f"Context:\n{context_text}\n\nQuestion: {query}"
    
    payload = {
        "model": "deepseek-chat", # or deepseek-reasoner
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 500
    }
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        answer = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM API Error: {str(e)}")
    
    # Extract unique sources
    seen_sources = set()
    sources = []
    for doc in results:
        src = doc.metadata.get('source_file')
        if src and src not in seen_sources:
            sources.append(src)
            seen_sources.add(src)

    return QueryResponse(answer=answer, sources=sources)
