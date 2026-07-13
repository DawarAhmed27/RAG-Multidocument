# SBP GPT: State Bank of Pakistan Circulars RAG Assistant

An advanced, production-grade Retrieval-Augmented Generation (RAG) system with a visual web dashboard designed to query, search, and verify compliance details from the State Bank of Pakistan (SBP) circulars. 

This project was built during an internship at Meezan Bank Limited.

---

## 🏛️ Project Architecture & Workflow

The system is built bottom-up through a multi-stage data processing and runtime execution pipeline:

```
[Web Crawler: main.js] --> [Clean-up: clean_data.py / find_listing_pages.py]
                                          |
                                          v
[ChromaDB Vector Store] <------- [Chunking: chunk.py] -------> [BM25 Pickle Index]
[BAAI/bge-small-en-v1.5]                  |                    [rank_bm25]
           |                              v
           |                      [Metadata Extraction]
           |                               |
           v                               v
[Contextual Retrieval Prefixes: generate_context.py]
           |
           +---------------------+
                                 |
                                 v
                     [Hybrid Search Fusion (RRF)]
                                 |
                                 v
                     [Sufficiency Checking Gate]
                                 |
                                 v
                    [Grounded Generation & Citation]
                                 |
                                 v
                    [FastAPI Backend: server.py]
                                 |
                                 v
                  [React Web Interface: SBP GPT UI]
```

1. **Scraping Layer (`src/crawlers/main.js`)**: Playwright and Crawlee index and download circular HTML pages into text documents.
2. **Filtering Layer (`clean_data.py` & `find_listing_pages.py`)**: Sanitizes data by removing binary/empty files and quarantining index/listing pages.
3. **Segmentation Layer (`chunk.py`)**: Adaptive chunker splits only long documents using paragraph snapping, keeping short documents in a single chunk.
4. **Metadata Extraction (`extract_metadata.py`)**: Regex-parses headers for circular numbers, departments, years, and dates, then merges them onto individual chunk records.
5. **Semantic Enrichment (`generate_context.py`)**: Pre-generates context prefixes for chunks (using a deterministic metadata prefix for single-chunk documents, and local LLM situating statements for multi-chunk documents).
6. **Indexing Layer (`build_embeddings.py` & `build_bm25.py`)**: Generates dense vector embeddings using `BAAI/bge-small-en-v1.5` in ChromaDB and compiles a sparse BM25 index.
7. **Search Broker (`hybrid_ret.py`)**: Merges dense and sparse candidates using **Reciprocal Rank Fusion (RRF)** and adds a metadata boost for exact circular queries.
8. **Anti-Hallucination Pipeline (`rag_answer.py`)**: Verifies sufficiency of context, restricts LLM answering to retrieved text only, and validates citation matches.
9. **Backend Server (`server.py`)**: FastAPI server that coordinates search inputs, dynamically routes parameters, and provides a mock LLM simulation fallback.
10. **Web UI (`frontend/`)**: React application with sand-gold design elements, live connection badges, an interactive citation drawer, and RAG diagnostics panels.

---

## 📂 Repository Structure

```
├── data/                       # Contains logs, scraped docs, and database files (git-ignored)
├── storage/                    # Scraper cache storage (git-ignored)
├── src/
│   ├── crawlers/
│   │   ├── scratch/            # Contains experimental and debug scripts
│   │   ├── main.js             # Playwright web scraper
│   │   ├── clean_data.py       # Data sanitization script
│   │   ├── find_listing_pages.py # Listing pages detector
│   │   ├── chunk.py            # Adaptive text chunker
│   │   ├── extract_metadata.py # Regex metadata extractor
│   │   ├── generate_context.py # Contextual prefix builder
│   │   ├── build_embeddings.py # ChromaDB indexer
│   │   ├── build_bm25.py       # BM25 keyword indexer
│   │   ├── hybrid_ret.py       # Search fusion engine
│   │   ├── rag_answer.py       # LLM generation and gating pipeline
│   │   └── server.py           # FastAPI server
│   └── utils/
├── frontend/                   # React + Vite web dashboard application
├── package.json                # Project script orchestrator
└── README.md                   # Project documentation
```

---

## 🚀 Setup & Execution Guide

### Prerequisites
* **Node.js** (v18+)
* **Python** (3.10+)
* **LM Studio** running locally on port `1234` with a loaded model (e.g. Llama-3.1 8B Instruct).

### Installation
1. Clone this repository.
2. Install Node dependencies at the root folder:
   ```bash
   npm install
   ```
3. Install frontend dependencies:
   ```bash
   cd frontend
   npm install
   cd ..
   ```
4. Configure Python virtual environment:
   Make sure you have `fastapi`, `uvicorn`, `chromadb`, `sentence-transformers`, and `rank-bm25` installed inside `src/crawlers/.venv`.

### Running the Application
To run the FastAPI server and the React dev server concurrently, run the following command in the project root:
```bash
npm run dev
```

* Backend Server will start at: `http://localhost:8000`
* Frontend Dashboard will open at: `http://localhost:5173`
