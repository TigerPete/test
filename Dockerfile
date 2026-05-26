# RAG agent — one image, two roles (query API vs ingest job).
#
# Query API (long-running, scale to zero in cloud):
#   docker run -p 8000:8000 -v ./data:/app/data -e OLLAMA_HOST=http://host.docker.internal:11434 \
#     rag-agent query
#
# Ingest job (run once, then exit):
#   docker run -v ./data:/app/data -e OLLAMA_HOST=http://host.docker.internal:11434 \
#     rag-agent ingest --reset

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY rag_agent/ rag_agent/
COPY app.py .

RUN mkdir -p data/documents/uploads data/output data/chroma_db

# Default: query API (override CMD for ingest job)
EXPOSE 8000
CMD ["uvicorn", "rag_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]

# Ingest entrypoint helper (used by compose / k8s Job)
# docker run ... rag-agent python -m rag_agent.main ingest --reset
