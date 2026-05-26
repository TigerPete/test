"""
Document intake: load files, split into chunks, embed, and store in Chroma.

Run once (or after documents change) via: python -m rag_agent.main ingest
Embeddings are expensive; persisting to CHROMA_DIR avoids re-processing on every question.
"""

from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_agent.config import CHUNK_OVERLAP, CHUNK_SIZE, DATA_DIR
from rag_agent.vector_store import get_vector_store


def load_documents(source_dir: Path | None = None) -> list[Document]:
    """
    Step 1 of intake: read raw files into LangChain Document objects.

    Each loader scans recursively (**) so subfolders like MaerskFiles/ are included.
    Metadata (e.g. source filename) travels with chunks for optional citation later.
    """
    source = source_dir or DATA_DIR
    source.mkdir(parents=True, exist_ok=True)

    # Separate loaders per extension because PDF parsing differs from plain text.
    loaders = [
        DirectoryLoader(
            str(source),
            glob="**/*.txt",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
        ),
        DirectoryLoader(
            str(source),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
        ),
        DirectoryLoader(
            str(source),
            glob="**/*.pdf",
            loader_cls=PyPDFLoader,
            show_progress=True,
        ),
    ]

    documents: list[Document] = []
    for loader in loaders:
        documents.extend(loader.load())

    return documents


def split_documents(documents: list[Document]) -> list[Document]:
    """
    Step 2 of intake: split long documents into smaller chunks.

    Whole PDFs are too large to embed or inject into the LLM at once. Overlap helps
    retrieval catch facts that span a page boundary between two chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    return splitter.split_documents(documents)


def ingest(source_dir: Path | None = None, reset: bool = False) -> int:
    """
    Full intake pipeline: load -> split -> embed -> persist in Chroma.

    reset=True deletes the old index first (use when documents change or you want a clean rebuild).
    Returns the number of chunks stored (e.g. 2043 for the Maersk corpus).
    """
    documents = load_documents(source_dir)
    if not documents:
        raise FileNotFoundError(
            f"No documents found in {source_dir or DATA_DIR}. "
            "Add .txt, .md, or .pdf files before running ingest."
        )

    chunks = split_documents(documents)

    # Step 3: Chroma embeds each chunk via Ollama and writes vectors to disk.
    store = get_vector_store(reset=reset)
    store.add_documents(chunks)

    return len(chunks)
