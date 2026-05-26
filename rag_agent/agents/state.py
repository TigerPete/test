"""
Shared workflow memory for the LangGraph pipeline.

TypedDict documents which keys exist and what each agent is expected to read/write.
LangGraph merges each agent's return dict into this state as the graph runs.
"""

from typing import TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict):
    # Set by the user / CLI before the graph starts.
    query: str

    # Filled by the writing agent after vector retrieval (raw chunks + draft text).
    context: list[Document]
    draft: str

    # Filled by the summarizing agent (short leadership-friendly version).
    summary: str

    # Filled by the publishing agent (filesystem path to the final markdown report).
    published_output: str
