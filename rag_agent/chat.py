"""
Fast chat path: retrieve relevant chunks and answer in one LLM call.

Used by the Streamlit "Quick chat" mode. The full three-agent pipeline
(writing -> summarizing -> publishing) is slower but produces a saved report.
"""

import json
import urllib.error
import urllib.request

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from rag_agent.config import CHAT_MODEL, CHROMA_DIR, EMBED_MODEL
from rag_agent.llm import get_chat_llm
from rag_agent.vector_store import get_retriever


def quick_answer(query: str) -> str:
    """
    Retrieve context and return a conversational answer (no report file).

    Single LLM call after semantic search — faster than the three-agent pipeline.
    """
    retriever = get_retriever()
    retrieved = retriever.invoke(query)
    context = "\n\n".join(doc.page_content for doc in retrieved)

    llm = get_chat_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a helpful assistant. Answer using only the provided document "
            "context. If the context does not contain enough information, say so clearly. "
            "Be concise and use plain language.",
        ),
        ("human", "Context:\n{context}\n\nQuestion:\n{query}"),
    ])
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": context, "query": query})


def check_ollama_status() -> tuple[bool, list[str], str]:
    """Return (is_ok, model_names, message) via the local Ollama HTTP API."""
    url = "http://127.0.0.1:11434/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            data = json.loads(response.read().decode())
        names = [m.get("name", "") for m in data.get("models", [])]
        if not names:
            return False, [], "Ollama is running but no models are installed."

        missing = []
        for required in (CHAT_MODEL, EMBED_MODEL):
            if not any(required in n for n in names):
                missing.append(required)
        if missing:
            return (
                False,
                names,
                f"Missing models (install in Ollama): {', '.join(missing)}",
            )
        return True, names, "Ollama is ready."
    except urllib.error.URLError as exc:
        return False, [], f"Cannot reach Ollama. Start the Ollama app. ({exc.reason})"
    except Exception as exc:
        return False, [], f"Ollama check failed: {exc}"


def index_exists() -> bool:
    """True if Chroma was created (user has indexed at least once)."""
    return (CHROMA_DIR / "chroma.sqlite3").exists()
