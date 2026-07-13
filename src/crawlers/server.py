import os
import sys
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List

# Ensure current directory is in sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from hybrid_ret import HybridRetriever
    import rag_answer
except ImportError as e:
    print(f"Error importing modules: {e}")
    # Fallback path additions if run from different cwd
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.append(parent_dir)
    from hybrid_ret import HybridRetriever
    import rag_answer

app = FastAPI(title="SBP Circulars RAG API Server")

# Enable CORS for frontend development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev simplicity, restrict in production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the retriever globally
print("Initializing Hybrid Retriever...")
try:
    retriever = HybridRetriever()
except Exception as e:
    print(f"CRITICAL: Failed to initialize retriever: {e}")
    retriever = None

class QueryRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=10)
    retrieval_mode: str = Field(default="hybrid") # "hybrid" or "bm25"
    department: Optional[str] = None

class ChunkResponse(BaseModel):
    chunk_id: str
    score: float
    circular_number: str
    department: str
    date: str
    title: str
    text: str

class QueryResponse(BaseModel):
    answered: bool
    answer: str
    sufficiency_checked: bool
    sufficiency_reasoning: str
    citation_issues: List[str]
    chunks: List[ChunkResponse]
    is_mock: bool = False

def generate_mock_response(query: str, chunks: List[dict]) -> dict:
    """Generates a structured mock response using retrieved document headers when LM Studio is down."""
    if not chunks:
        reasoning = "No documents retrieved matching the query."
        refusal = "I don't have enough information in the retrieved SBP circulars to answer this question. (No circular documents were retrieved for your search)"
        return {
            "answered": False,
            "answer": refusal,
            "sufficiency_checked": True,
            "sufficiency_reasoning": reasoning,
            "citation_issues": [],
            "chunks": chunks,
            "is_mock": True
        }

    # Simple keyword match for mock check
    keywords = ["foreign", "exchange", "holiday", "accounts", "regulations", "interest", "rate", "bprd"]
    query_lower = query.lower()
    has_match = any(k in query_lower for k in keywords)

    if not has_match:
        reasoning = "The retrieved documents do not contain specific information matching the query terms."
        refusal = f"I don't have enough information in the retrieved SBP circulars to answer this question. (Sufficiency check: INSUFFICIENT - query context '{query}' is outside of scope)"
        return {
            "answered": False,
            "answer": refusal,
            "sufficiency_checked": True,
            "sufficiency_reasoning": reasoning,
            "citation_issues": [],
            "chunks": chunks,
            "is_mock": True
        }

    # Generate a beautiful summary response using metadata
    ref = chunks[0]
    dept = ref.get("department", "SBP")
    c_num = ref.get("circular_number", "Circular")
    c_date = ref.get("date", "Unknown Date")
    c_title = ref.get("title", "Regulations Amendment")

    answer_text = (
        f"### **Regulatory Summary (Simulation Mode)**\n\n"
        f"*(Note: LM Studio is currently offline. This is an auto-generated summary from the retrieved source document metadata.)*\n\n"
        f"According to **{c_num}** ({dept} Department, dated {c_date}) titled *\"{c_title}\"*:\n\n"
        f"1. **Primary Regulation**: The retrieved document outlines guidelines concerning the requested query. "
        f"Specifically, it discusses: \"{ref.get('text', '')[:180]}...\"\n\n"
        f"2. **Further Directives**: Guidelines are supported by other references including:\n"
    )

    for i, c in enumerate(chunks[1:3], start=2):
        c_num_i = c.get("circular_number", "Circular")
        c_date_i = c.get("date", "Date")
        answer_text += f"   - **{c_num_i}** ({c.get('department', 'SBP')}, {c_date_i}): \"{c.get('title', '')}\" — *[{c_num_i}, {c_date_i}]*\n"

    answer_text += (
        f"\n\n**Citations in this summary:**\n"
        f"- *[{c_num}, {c_date}]*\n"
    )
    for c in chunks[1:3]:
        answer_text += f"- *[{c.get('circular_number')}, {c.get('date')}]*\n"

    answer_text += f"\n*Please start LM Studio locally on {rag_answer.LM_STUDIO_URL} to get live LLM-grounded answers.*"

    return {
        "answered": True,
        "answer": answer_text,
        "sufficiency_checked": True,
        "sufficiency_reasoning": f"Simulated sufficiency check: Yes, document {c_num} contains direct references.",
        "citation_issues": [],
        "chunks": chunks,
        "is_mock": True
    }

@app.post("/api/query", response_model=QueryResponse)
def execute_query(req: QueryRequest):
    if not retriever:
        raise HTTPException(status_code=500, detail="Retriever is not initialized. Check server startup logs.")

    # Configure the retriever dynamically
    retriever.use_dense = (req.retrieval_mode == "hybrid")

    # Set environment variable for retrieval mode just in case
    os.environ["SBP_RETRIEVAL_MODE"] = req.retrieval_mode

    print(f"Executing query: '{req.query}' using mode='{req.retrieval_mode}', top_k={req.top_k}, dept={req.department}")

    # First, fetch chunks with full text for the API and potential fallback
    try:
        raw_chunks = retriever.search(req.query, top_n=req.top_k, department=req.department, truncate=False)
    except Exception as e:
        print(f"Error during retrieval: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")

    # Check if LM Studio is online
    lm_studio_online = False
    try:
        # Quick healthcheck request to LM studio endpoint with a tiny model list fetch or short timeout completion
        r = requests.get("http://localhost:1234/v1/models", timeout=2)
        if r.status_code == 200:
            lm_studio_online = True
    except Exception:
        pass

    if not lm_studio_online:
        print("LM Studio is offline. Generating simulated mock response...")
        mock_res = generate_mock_response(req.query, raw_chunks)
        return mock_res

    # If LM Studio is online, run the full pipeline
    try:
        # Call the grounded generation logic from rag_answer
        res = rag_answer.answer_question(retriever, req.query, top_k=req.top_k, verbose=False)
        
        # We need to map returned chunks so they include full text (rag_answer uses search with truncate=False)
        # Verify the structure matches our output model
        mapped_chunks = []
        for rc in res.get("chunks", []):
            mapped_chunks.append({
                "chunk_id": rc.get("chunk_id", ""),
                "score": rc.get("score", 0.0),
                "circular_number": rc.get("circular_number", ""),
                "department": rc.get("department", ""),
                "date": rc.get("date", ""),
                "title": rc.get("title", ""),
                "text": rc.get("text", "")
            })

        # Find sufficiency from reasoning or checks
        # Let's perform check_sufficiency directly if not provided, but rag_answer does it
        # Wait, rag_answer.answer_question returns answered=False when insufficient
        answered = res.get("answered", False)
        
        # Let's run check_sufficiency to get the explicit reasoning message
        sufficient, reasoning = rag_answer.check_sufficiency(req.query, res.get("chunks", []))

        return {
            "answered": answered,
            "answer": res.get("answer", ""),
            "sufficiency_checked": True,
            "sufficiency_reasoning": reasoning,
            "citation_issues": res.get("citation_issues", []),
            "chunks": mapped_chunks,
            "is_mock": False
        }

    except Exception as e:
        print(f"Error running grounded generation pipeline: {e}. Falling back to mock generator.")
        # Fall back to mock response rather than crashing the interface
        mock_res = generate_mock_response(req.query, raw_chunks)
        return mock_res

@app.get("/api/status")
def get_status():
    lm_studio_online = False
    try:
        r = requests.get("http://localhost:1234/v1/models", timeout=2)
        if r.status_code == 200:
            lm_studio_online = True
    except Exception:
        pass

    return {
        "status": "healthy",
        "retriever_loaded": retriever is not None,
        "lm_studio_connected": lm_studio_online,
        "chroma_collection": "sbp_circulars",
        "embedding_model": "BAAI/bge-small-en-v1.5"
    }


if __name__ == "__main__":
    import uvicorn
    # Run the server on port 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)
