"""
LangGraph orchestration: wires the three agents into a linear pipeline.

LangGraph passes a shared GraphState dict from node to node. Each agent returns
only the fields it updates; LangGraph merges them into the running state.
"""

from functools import partial

from langgraph.graph import END, START, StateGraph

from rag_agent.agents.publishing import publishing_agent
from rag_agent.agents.state import GraphState
from rag_agent.agents.summarizing import summarizing_agent
from rag_agent.agents.writing import writing_agent
from rag_agent.vector_store import get_retriever


def build_graph():
    """
    Define nodes (agents) and edges (execution order).

    partial() injects the retriever into writing_agent because LangGraph nodes
    only receive state by default; the retriever is shared infrastructure.
    """
    retriever = get_retriever()
    graph = StateGraph(GraphState)

    graph.add_node("writing", partial(writing_agent, retriever=retriever))
    graph.add_node("summarizing", summarizing_agent)
    graph.add_node("publishing", publishing_agent)

    # Fixed pipeline: retrieve+draft -> executive summary -> formatted report file.
    graph.add_edge(START, "writing")
    graph.add_edge("writing", "summarizing")
    graph.add_edge("summarizing", "publishing")
    graph.add_edge("publishing", END)

    return graph.compile()


def run_analysis(query: str) -> GraphState:
    """
    Run the full multi-agent pipeline for one user question.

    Initial state only needs query; each agent adds context, draft, summary, and path.
    """
    app = build_graph()
    return app.invoke({"query": query})
