"""
Agent 1 — Writing: retrieval-augmented draft generation.

This is the core RAG step: the user's question is embedded and matched against
stored chunks; only those passages are sent to the LLM, grounding the answer in
your documents instead of the model's general training data.
"""

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import VectorStoreRetriever

from rag_agent.agents.state import GraphState
from rag_agent.llm import get_chat_llm


def _format_context(docs: list[Document]) -> str:
    parts: list[str] = []
    for d in docs:
        source = d.metadata.get("source", "unknown")
        page = d.metadata.get("page", None)
        page_str = f", page {page + 1}" if isinstance(page, int) else ""
        parts.append(f"[source: {source}{page_str}]\n{d.page_content}")
    return "\n\n---\n\n".join(parts)


def writing_agent(state: GraphState, retriever: VectorStoreRetriever) -> dict:
    """
    Retrieve relevant chunks, then generate a structured technical draft.

    Returns partial state updates (context + draft) that LangGraph merges into GraphState.
    """
    query = state["query"]

    # Semantic search: find chunks whose embeddings are closest to the question.
    retrieved_docs: list[Document] = retriever.invoke(query)

    # Flatten chunk text for the prompt (metadata like source file is not shown to the model here).
    formatted_context = _format_context(retrieved_docs)

    llm = get_chat_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are an expert technical writer. Use the provided context to write "
            "a structured, comprehensive technical draft. If the context does not "
            "contain the answer, state that you do not have enough information.",
        ),
        ("human", "Context:\n{context}\n\nTask:\n{query}"),
    ])

    # LCEL chain: prompt template -> Ollama -> plain string output.
    chain = prompt | llm | StrOutputParser()
    generated_draft = chain.invoke({"context": formatted_context, "query": query})

    return {"context": retrieved_docs, "draft": generated_draft}
