"""
RAG agent package: local document Q&A with Ollama, Chroma, and a three-agent LangGraph pipeline.

  ingest   -> load PDFs, chunk, embed, save to data/chroma_db
  analyze  -> writing -> summarizing -> publishing -> data/output/report_*.md
"""
