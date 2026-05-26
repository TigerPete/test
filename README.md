# Document Q&A (Local RAG)

Ask questions about your own PDFs and text files using AI that runs **on your computer**—no cloud upload of documents.

Built with **Ollama**, **LangChain**, **Chroma**, and **LangGraph** (three-agent reports).

---

## For everyone (no terminal)

### What you need once

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/) (check “Add Python to PATH” during install).
2. **Ollama** — [ollama.com/download](https://ollama.com/download). Open the Ollama app and leave it running.
3. In Ollama, install these models (search in the app or use its library):
   - `llama3.2:3b` (answers questions)
   - `nomic-embed-text` (search index)

### First-time setup (one click)

1. Download or clone this folder.
2. Double-click **`setup.bat`** and wait until it finishes.

### Every time you use the app

1. Start **Ollama** (Start menu → Ollama).
2. Double-click **`run.bat`** — your browser opens the app.
3. In the sidebar:
   - **Upload** your PDF / `.txt` / `.md` files
   - Click **Index documents** (do this again after adding new files)
4. Type a question in the chat.

| Mode | Best for |
|------|----------|
| **Quick chat** | Fast answers in the window |
| **Full report** | Executive summary + saved markdown file (slower, 5–20 min) |

### Important

- **Do not commit copyrighted PDFs to GitHub.** Add your own documents locally only.
- First indexing can take **several minutes** depending on file size.
- Keep Ollama running while you use the app.

---

## For developers (CLI)

Create the venv and install deps (if not using `setup.bat`):

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
.venv\Scripts\python.exe -m rag_agent.main ingest
.venv\Scripts\python.exe -m rag_agent.main analyze "Your question"
```

Always use `.venv\Scripts\python.exe`, not plain `python`, on Windows.

---

## How it works

```
Upload PDFs → Index (Chroma + Ollama embeddings) → Ask a question
                                                      ↓
                              Quick chat: retrieve + one LLM answer
                              Full report: writing → summary → publish → .md file
```

| Path | Purpose |
|------|---------|
| `app.py` | Streamlit UI (primary) |
| `rag_agent/chat.py` | Fast `quick_answer()` for chat mode |
| `rag_agent/intake.py` | Load, chunk, embed documents |
| `rag_agent/graph.py` | Three-agent pipeline for full reports |
| `data/documents/uploads/` | Files uploaded via the UI |
| `data/chroma_db/` | Saved search index (local only) |
| `data/output/` | Generated report files |

Edit `rag_agent/config.py` to change models, chunk size, or retrieval depth.

### CUDA out of memory

Use `llama3.2:3b` (default) or set `CHAT_NUM_GPU = 0` in `config.py` for CPU-only inference.

---

## GitHub

This repo is meant to be shared **without** user documents or the vector index. `.gitignore` excludes PDFs, `chroma_db/`, and generated reports. Users add their own files and click **Index documents** after cloning.
