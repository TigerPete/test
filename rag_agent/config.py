"""
Central configuration for paths, models, and RAG tuning.

Keeping settings here (instead of scattered in agents) makes it easy to swap
models, point at a different document folder, or tune retrieval without touching
the pipeline logic.

Kubernetes: override via ConfigMap (see k8s/configmap.yaml).
"""

import os
from pathlib import Path


def _env_str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw is not None else default


def _env_optional_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return None
    return int(raw)


# --- Ollama connection (Docker / K8s) ---
OLLAMA_BASE_URL = os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_BASE_URL") or None

# --- Paths ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(_env_str("DATA_DIR", str(PROJECT_ROOT / "data" / "documents")))
UPLOADS_DIR = DATA_DIR / "uploads"
CHROMA_DIR = Path(_env_str("CHROMA_DIR", str(PROJECT_ROOT / "data" / "chroma_db")))
COLLECTION_NAME = _env_str("COLLECTION_NAME", "rag_documents")

# --- Ollama models ---
CHAT_MODEL = _env_str("CHAT_MODEL", "llama3.2:3b")
EMBED_MODEL = _env_str("EMBED_MODEL", "nomic-embed-text")
CHAT_TEMPERATURE = _env_float("CHAT_TEMPERATURE", 0.3)
CHAT_NUM_CTX = _env_int("CHAT_NUM_CTX", 8192)
CHAT_NUM_GPU = _env_optional_int("CHAT_NUM_GPU")

# --- Chunking (intake) ---
CHUNK_SIZE = _env_int("CHUNK_SIZE", 1800)
CHUNK_OVERLAP = _env_int("CHUNK_OVERLAP", 350)

# --- Retrieval ---
RETRIEVAL_K = _env_int("RETRIEVAL_K", 16)
