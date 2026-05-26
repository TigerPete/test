"""
Shared Ollama chat client for all three analysis agents.

One factory keeps model name, temperature, and GPU settings consistent so each
agent step behaves the same way and VRAM settings only need to change in config.py.
"""

from langchain_ollama import ChatOllama

from rag_agent.config import (
    CHAT_MODEL,
    CHAT_NUM_CTX,
    CHAT_NUM_GPU,
    CHAT_TEMPERATURE,
    OLLAMA_BASE_URL,
)


def get_chat_llm() -> ChatOllama:
    """
    Build a ChatOllama instance pointed at the local Ollama server.

    num_ctx caps prompt size (draft + context can be large after retrieval).
    num_gpu=0 (when set in config) forces CPU inference to avoid CUDA OOM on small GPUs.
    """
    kwargs: dict = {
        "model": CHAT_MODEL,
        "temperature": CHAT_TEMPERATURE,
        "num_ctx": CHAT_NUM_CTX,
    }
    if CHAT_NUM_GPU is not None:
        kwargs["num_gpu"] = CHAT_NUM_GPU
    if OLLAMA_BASE_URL:
        kwargs["base_url"] = OLLAMA_BASE_URL
    return ChatOllama(**kwargs)
