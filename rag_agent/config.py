"""
Central configuration for paths, models, and RAG tuning.

Keeping settings here (instead of scattered in agents) makes it easy to swap
models, point at a different document folder, or tune retrieval without touching
the pipeline logic.
"""

from pathlib import Path

# --- Paths ---
# PROJECT_ROOT is the repo root (parent of the rag_agent package).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Raw files to ingest live here (PDFs, .txt, .md).
DATA_DIR = PROJECT_ROOT / "data" / "documents"
# Web UI uploads land here (included when indexing DATA_DIR).
UPLOADS_DIR = DATA_DIR / "uploads"
# Chroma persists embeddings to disk so ingest only needs to run once per corpus.
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_db"
COLLECTION_NAME = "rag_documents"

# --- Ollama models (must be pulled locally: ollama pull <name>) ---
# Chat model answers questions; embedding model converts text chunks to vectors.
# llama3 needs ~6GB+ VRAM; llama3.2:3b fits smaller GPUs.
CHAT_MODEL = "llama3.2:3b"
EMBED_MODEL = "nomic-embed-text"
CHAT_TEMPERATURE = 0.3  # Lower = more factual/consistent; higher = more creative.
CHAT_NUM_CTX = 8192  # Context window size; smaller uses less VRAM.
# None = Ollama decides GPU layers; 0 = force CPU (slower, avoids CUDA OOM).
CHAT_NUM_GPU = None

# --- Chunking (intake) ---
# Documents are split so each chunk fits in the model context and retrieval stays focused.
CHUNK_SIZE = 1800  # Characters per chunk (approximate; splitter respects boundaries).
CHUNK_OVERLAP = 350  # Overlap preserves sentences that would otherwise be cut in half.

# --- Retrieval (analyze) ---
# How many chunks the writing agent pulls per question (trade-off: coverage vs. speed/VRAM).
RETRIEVAL_K = 16
