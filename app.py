"""
Document Q&A — browser UI (no terminal required for daily use).

Start: double-click run.bat
"""

from __future__ import annotations

import traceback
from pathlib import Path

import streamlit as st

from rag_agent.chat import check_ollama_status, index_exists, quick_answer
from rag_agent.config import CHAT_MODEL, DATA_DIR, EMBED_MODEL, UPLOADS_DIR
from rag_agent.graph import run_analysis
from rag_agent.intake import ingest

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="Document Q&A", page_icon="📄", layout="wide")
st.title("Document Q&A")
st.caption("Upload documents, index them once, then ask questions in plain English. All processing stays on this computer.")

if "messages" not in st.session_state:
    st.session_state.messages: list[dict] = []

# --- Sidebar ---
with st.sidebar:
    st.header("Getting started")
    st.markdown(
        """
        1. Open **Ollama** from the Start menu (leave it running).
        2. **Upload** your files below.
        3. Click **Index documents**.
        4. Ask a question in the chat.
        """
    )

    st.subheader("Ollama status")
    ollama_ok, model_list, ollama_msg = check_ollama_status()
    if ollama_ok:
        st.success(ollama_msg)
        with st.expander("Installed models"):
            st.write(", ".join(model_list))
    else:
        st.error(ollama_msg)
        st.info(f"Required in Ollama: **{CHAT_MODEL}**, **{EMBED_MODEL}**")

    st.divider()
    st.header("Your documents")
    uploaded = st.file_uploader(
        "Upload PDF, TXT, or Markdown",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
    )
    if uploaded:
        for f in uploaded:
            (UPLOADS_DIR / f.name).write_bytes(f.getvalue())
        st.success(f"Saved {len(uploaded)} file(s). Click **Index documents** to search them.")

    st.divider()
    st.header("Index")
    rebuild = st.checkbox("Rebuild index from scratch", value=False)
    if st.button("Index documents", type="primary", use_container_width=True):
        if not ollama_ok:
            st.error("Start Ollama before indexing.")
        else:
            with st.spinner("Building search index… This may take several minutes."):
                try:
                    count = ingest(source_dir=DATA_DIR, reset=rebuild)
                    st.success(f"Indexed **{count}** sections. You can ask questions now.")
                except FileNotFoundError:
                    st.error("No documents found. Upload files above first.")
                except Exception as exc:
                    st.error(f"Indexing failed: {exc}")
                    with st.expander("Technical details"):
                        st.code(traceback.format_exc())

    if index_exists():
        st.success("Search index is ready.")
    else:
        st.warning("No index yet. Upload files, then click **Index documents**.")

    st.divider()
    mode = st.radio(
        "Answer mode",
        ["Quick chat (faster)", "Full report (summary + saved file)"],
        help="Quick chat: one fast answer. Full report: summary plus a markdown file (5–20 min).",
    )

# --- Chat ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("report_path"):
            path = Path(msg["report_path"])
            if path.exists():
                st.download_button(
                    "Download report",
                    data=path.read_text(encoding="utf-8"),
                    file_name=path.name,
                    mime="text/markdown",
                    key=f"dl_{path.name}_{msg.get('id', '')}",
                )

if prompt := st.chat_input("Ask a question about your documents…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not ollama_ok:
            reply = "Start the **Ollama** app, then try again."
            st.error(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        elif not index_exists():
            reply = "Upload documents and click **Index documents** in the sidebar first."
            st.warning(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
        else:
            try:
                if mode.startswith("Quick"):
                    with st.spinner("Searching documents and generating answer…"):
                        reply = quick_answer(prompt)
                    st.markdown(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})
                else:
                    with st.spinner(
                        "Running full report (writing → summary → publish). "
                        "This may take 5–20 minutes…"
                    ):
                        result = run_analysis(prompt)
                    report_path = result.get("published_output", "")
                    reply = (
                        f"### Executive summary\n\n{result.get('summary', '')}\n\n---\n\n"
                        f"Full report saved to:\n\n`{report_path}`"
                    )
                    st.markdown(reply)
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": reply,
                            "report_path": report_path,
                            "id": str(len(st.session_state.messages)),
                        }
                    )
            except Exception as exc:
                err = (
                    f"Something went wrong: {exc}\n\n"
                    f"Check that Ollama is running and **{CHAT_MODEL}** is installed."
                )
                st.error(err)
                st.session_state.messages.append({"role": "assistant", "content": err})

if st.sidebar.button("Clear chat"):
    st.session_state.messages = []
    st.rerun()
