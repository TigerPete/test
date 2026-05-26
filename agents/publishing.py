"""
Agent 3 — Publishing: format and save the final deliverable.

Combines the executive summary and full draft into one markdown file suitable for
sharing (email, deck appendix, or repo artifact). Each run gets a timestamped path
so prior reports are never overwritten.
"""

from datetime import datetime, timezone
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from rag_agent.agents.state import GraphState
from rag_agent.config import PROJECT_ROOT
from rag_agent.llm import get_chat_llm

OUTPUT_DIR = PROJECT_ROOT / "data" / "output"


def publishing_agent(state: GraphState) -> dict:
    """
    Merge summary + draft into publish-ready markdown and write to disk.

    The LLM pass improves structure/titles; the file write is what makes the output
    easy to find and attach when presenting to a boss or coworkers.
    """
    query = state["query"]
    draft = state["draft"]
    summary = state["summary"]

    llm = get_chat_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a publishing editor. Combine the executive summary and full "
            "draft into a single, well-structured markdown document suitable for "
            "distribution. Include a title, summary section, and full content section.",
        ),
        (
            "human",
            "Task: {query}\n\nExecutive summary:\n{summary}\n\nFull draft:\n{draft}",
        ),
    ])
    chain = prompt | llm | StrOutputParser()
    published = chain.invoke({"query": query, "summary": summary, "draft": draft})

    # Persist artifact: UTC timestamp avoids collisions across runs on the same day.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUT_DIR / f"report_{timestamp}.md"
    output_path.write_text(published, encoding="utf-8")

    # Path is stored in state so main.py can print where to open the report.
    return {"published_output": str(output_path)}
