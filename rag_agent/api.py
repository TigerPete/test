"""
HTTP query API for cloud-style deployments (scale-to-zero friendly).

Run locally:
  .venv\\Scripts\\python.exe -m uvicorn rag_agent.api:app --host 0.0.0.0 --port 8000

Endpoints:
  GET  /health          — liveness
  GET  /ready             — Ollama + vector index checks
  POST /v1/chat           — quick RAG answer (one LLM call)
  POST /v1/analyze        — full three-agent report pipeline
  POST /v1/ingest         — build/rebuild index (batch-style; can be slow)

Ingest is also available as a one-shot container job:
  python -m rag_agent.main ingest [--reset]
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag_agent.chat import check_ollama_status, index_exists, quick_answer
from rag_agent.config import DATA_DIR
from rag_agent.graph import run_analysis
from rag_agent.intake import ingest

app = FastAPI(
    title="RAG Agent API",
    description="Query and ingest boundaries for container / cloud deployment.",
    version="0.1.0",
)


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Question about indexed documents")


class ChatResponse(BaseModel):
    answer: str


class AnalyzeRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Task or question for the full report pipeline")


class AnalyzeResponse(BaseModel):
    summary: str
    published_output: str


class IngestRequest(BaseModel):
    reset: bool = Field(False, description="Delete existing Chroma data before ingesting")
    source: str | None = Field(None, description=f"Document directory (default: {DATA_DIR})")


class IngestResponse(BaseModel):
    chunks: int


class ReadyResponse(BaseModel):
    ready: bool
    ollama_ok: bool
    index_ready: bool
    message: str


def _require_ollama() -> None:
    ok, _, msg = check_ollama_status()
    if not ok:
        raise HTTPException(status_code=503, detail=msg)


def _require_index() -> None:
    if not index_exists():
        raise HTTPException(
            status_code=503,
            detail="Vector index not found. Run ingest first (POST /v1/ingest or ingest job).",
        )


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe — process is up (does not check Ollama or index)."""
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyResponse)
def ready() -> ReadyResponse:
    """Readiness: Ollama reachable with required models and Chroma index exists."""
    ollama_ok, _, ollama_msg = check_ollama_status()
    index_ready = index_exists()
    ready_flag = ollama_ok and index_ready
    if ready_flag:
        message = "Ready for chat and analyze."
    elif not ollama_ok:
        message = ollama_msg
    else:
        message = "Ollama OK but index missing — run ingest."
    return ReadyResponse(
        ready=ready_flag,
        ollama_ok=ollama_ok,
        index_ready=index_ready,
        message=message,
    )


@app.post("/v1/chat", response_model=ChatResponse)
def chat(body: ChatRequest) -> ChatResponse:
    """Retrieve relevant chunks and return one conversational answer."""
    _require_ollama()
    _require_index()
    try:
        answer = quick_answer(body.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ChatResponse(answer=answer)


@app.post("/v1/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """Run writing → summarizing → publishing pipeline; may take many minutes."""
    _require_ollama()
    _require_index()
    try:
        result = run_analysis(body.query)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AnalyzeResponse(
        summary=result.get("summary", ""),
        published_output=result.get("published_output", ""),
    )


@app.post("/v1/ingest", response_model=IngestResponse)
def ingest_documents(body: IngestRequest) -> IngestResponse:
    """
    Load, chunk, embed, and persist documents (same as CLI ingest).

    Intended for batch/job invocation; HTTP request blocks until complete.
    For large corpora, prefer: python -m rag_agent.main ingest --reset
    """
    _require_ollama()
    source = Path(body.source) if body.source else None
    try:
        count = ingest(source_dir=source, reset=body.reset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IngestResponse(chunks=count)
