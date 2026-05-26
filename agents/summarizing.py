"""
Agent 2 — Summarizing: executive summary of the writing agent's draft.

Runs after the draft exists but does not re-query the vector store. It compresses
the long answer for stakeholders who want highlights, not the full technical depth.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from rag_agent.agents.state import GraphState
from rag_agent.llm import get_chat_llm


def summarizing_agent(state: GraphState) -> dict:
    """
    Condense the draft into a short executive summary.

    Uses the original query for framing so the summary stays aligned with what was asked.
    """
    draft = state["draft"]
    query = state["query"]

    llm = get_chat_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert editor. Produce a concise executive summary of the "
            "draft. Highlight key findings, recommendations, and open questions. "
            "Keep the summary under 300 words.",
        ),
        ("human", "Original task:\n{query}\n\nDraft to summarize:\n{draft}"),
    ])
    chain = prompt | llm | StrOutputParser()
    summary = chain.invoke({"query": query, "draft": draft})

    return {"summary": summary}
