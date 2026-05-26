"""
Vector database layer: Chroma + Ollama embeddings.

At query time we do not re-read PDFs; we search this index for chunks whose
embedding vectors are closest to the question (semantic similarity).
"""

import shutil

from langchain_chroma import Chroma
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_ollama import OllamaEmbeddings

from rag_agent.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBED_MODEL,
    OLLAMA_BASE_URL,
    RETRIEVAL_K,
)


def get_embeddings() -> OllamaEmbeddings:
    """Same embedding model must be used for ingest and retrieval or search quality breaks."""
    kwargs: dict = {"model": EMBED_MODEL}
    if OLLAMA_BASE_URL:
        kwargs["base_url"] = OLLAMA_BASE_URL
    return OllamaEmbeddings(**kwargs)


def get_vector_store(reset: bool = False) -> Chroma:
    """
    Open (or recreate) the persisted Chroma collection.

    persist_directory means the index survives restarts—this is how you "save" the RAG
    without re-ingesting. reset=True wipes CHROMA_DIR before a fresh ingest.
    """
    if reset and CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def get_retriever() -> VectorStoreRetriever:
    """
    Retriever used by the writing agent: turns a natural-language query into top-k chunks.

    k=RETRIEVAL_K limits how much context fits in the LLM prompt (and runtime).
    """
    store = get_vector_store()
    fetch_k = max(40, RETRIEVAL_K * 4)
    return store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": RETRIEVAL_K,
            "fetch_k": fetch_k,
            "lambda_mult": 0.5,
        },
    )
