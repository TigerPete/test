"""
CLI entry point: ingest (build index) and analyze (run three-agent pipeline).

Usage:
  .venv\\Scripts\\python.exe -m rag_agent.main ingest
  .venv\\Scripts\\python.exe -m rag_agent.main analyze "your question"
"""

import argparse
import sys
from pathlib import Path

from rag_agent.config import CHAT_MODEL, DATA_DIR, PROJECT_ROOT

# Dependencies live in .venv; system Python lacks langchain/langgraph packages.
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"


def _ensure_venv() -> None:
    """Warn when using system Python instead of the project virtualenv."""
    if not VENV_PYTHON.exists():
        return
    if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
        print(
            "Warning: not using the project virtualenv.\n"
            f"  Current:  {sys.executable}\n"
            f"  Expected: {VENV_PYTHON}\n\n"
            "Run commands with:\n"
            "  .venv\\Scripts\\python.exe -m rag_agent.main <command>\n",
            file=sys.stderr,
        )


def _import_run_analysis():
    # Lazy import: ingest does not need langgraph; avoids import errors on wrong Python.
    from rag_agent.graph import run_analysis

    return run_analysis


def cmd_ingest(args: argparse.Namespace) -> None:
    """Handle: python -m rag_agent.main ingest [--source PATH] [--reset]"""
    from rag_agent.intake import ingest

    source = Path(args.source) if args.source else None
    count = ingest(source_dir=source, reset=args.reset)
    print(f"Ingested {count} chunks into the vector database.")


def cmd_analyze(args: argparse.Namespace) -> None:
    """
    Handle: python -m rag_agent.main analyze "question"

    Runs all three agents sequentially; terminal stays quiet until finished.
    Final report path is printed so you can open data/output/report_*.md.
    """
    run_analysis = _import_run_analysis()
    result = run_analysis(args.query)
    print("\n--- Executive Summary ---\n")
    print(result["summary"])
    print("\n--- Published Output ---\n")
    print(f"Saved to: {result['published_output']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG agent with Ollama, Chroma, and LangGraph multi-agent pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest_parser = sub.add_parser("ingest", help="Load documents into the vector store")
    ingest_parser.add_argument(
        "--source",
        help=f"Directory of documents (default: {DATA_DIR})",
    )
    ingest_parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing Chroma data before ingesting",
    )
    ingest_parser.set_defaults(func=cmd_ingest)

    analyze_parser = sub.add_parser("analyze", help="Run the three-agent analysis pipeline")
    analyze_parser.add_argument("query", help="Analysis task or question")
    analyze_parser.set_defaults(func=cmd_analyze)

    args = parser.parse_args()
    _ensure_venv()
    try:
        args.func(args)
    except ModuleNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "\nDependencies are installed in .venv. Use:\n"
            "  .venv\\Scripts\\python.exe -m rag_agent.main ingest\n"
            "  .venv\\Scripts\\python.exe -m rag_agent.main analyze \"your question\"",
            file=sys.stderr,
        )
        sys.exit(1)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        print(
            "\nEnsure Ollama is running and models are pulled:\n"
            f"  ollama pull {CHAT_MODEL}\n"
            "  ollama pull nomic-embed-text\n"
            "\nCUDA OOM? Use a smaller CHAT_MODEL in config.py (e.g. llama3.2:3b) or set CHAT_NUM_GPU = 0",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
