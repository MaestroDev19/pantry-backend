from __future__ import annotations

import logging
from typing import Any

import anyio
from langchain.tools import tool
from langchain_community.vectorstores import SupabaseVectorStore

from pantry_server.contexts.ai.infrastructure.vector_store import get_vector_store
from pantry_server.core.exceptions import AppError
from pantry_server.shared.contracts import RecipeWorkflowInput, ShoppingWorkflowInput

LOGGER = logging.getLogger(__name__)

DEFAULT_RETRIEVAL_K = 5
RETRIEVAL_TIMEOUT_SECONDS = 4.0

RECIPE_KNOWLEDGE_BASE = [
    "Tomato and olive oil pair well with rice and pasta.",
    "Use pantry staples first to reduce waste.",
    "Seasoning in layers improves flavor.",
]

SHOPPING_KNOWLEDGE_BASE = [
    "For tomato pasta, keep garlic, tomato, olive oil, and salt in stock.",
    "Batch shopping by staple categories reduces missed items.",
    "Missing ingredients should be prioritized by recipe goal relevance.",
]


def _serialize_documents(retrieved_docs: list[Any]) -> tuple[str, list[str]]:
    chunks = [
        f"Source: {doc.metadata}\nContent: {doc.page_content}"
        for doc in retrieved_docs
    ]
    serialized = "\n\n".join(chunks)
    return serialized, chunks


def _search_and_serialize(
    vector_store: SupabaseVectorStore,
    query: str,
    *,
    k: int,
) -> tuple[str, list[str]]:
    retrieved_docs = vector_store.similarity_search(query, k=k)
    return _serialize_documents(retrieved_docs)


def build_retrieve_context_tool(vector_store: SupabaseVectorStore, *, k: int = DEFAULT_RETRIEVAL_K):
    @tool(response_format="content_and_artifact")
    def retrieve_context_for_query(query: str) -> tuple[str, list[Any]]:
        """Retrieve information to help answer a query."""
        return _search_and_serialize(vector_store, query, k=k)

    return retrieve_context_for_query


def _keyword_fallback(query: str, knowledge_base: list[str], *, k: int) -> list[str]:
    tokens = {token.strip().lower() for token in query.split() if token.strip()}
    ranked = sorted(
        knowledge_base,
        key=lambda chunk: sum(token in chunk.lower() for token in tokens),
        reverse=True,
    )
    return ranked[:k]


async def retrieve_context(
    query: str,
    *,
    k: int = DEFAULT_RETRIEVAL_K,
    fallback_knowledge: list[str] | None = None,
) -> list[str]:
    normalized_query = query.strip()
    if not normalized_query:
        return []

    try:
        vector_store = await get_vector_store()
    except AppError:
        LOGGER.warning("Vector store unavailable; using keyword fallback for retrieval.")
        if fallback_knowledge:
            return _keyword_fallback(normalized_query, fallback_knowledge, k=k)
        return []

    def _run_search() -> list[str]:
        _serialized, chunks = _search_and_serialize(vector_store, normalized_query, k=k)
        return chunks

    try:
        with anyio.fail_after(RETRIEVAL_TIMEOUT_SECONDS):
            chunks = await anyio.to_thread.run_sync(_run_search)
    except Exception:
        LOGGER.exception("Vector retrieval failed; using keyword fallback.")
        if fallback_knowledge:
            return _keyword_fallback(normalized_query, fallback_knowledge, k=k)
        return []

    if chunks:
        return chunks
    if fallback_knowledge:
        return _keyword_fallback(normalized_query, fallback_knowledge, k=k)
    return []


def build_recipe_query(request: RecipeWorkflowInput) -> str:
    parts = [*request.pantry_items, *request.dietary_preferences]
    return " ".join(parts).strip() or "pantry recipe"


def build_shopping_query(request: ShoppingWorkflowInput) -> str:
    items = " ".join(request.pantry_items)
    return f"{request.recipe_goal} {items}".strip()
