from __future__ import annotations

from typing import List, Tuple
from uuid import UUID

from langchain.tools import tool
from langchain_core.documents import Document

from pantry_backend.ai.retriever_cache import get_retriever_cache
from pantry_backend.vectorstores.supabase_vector_store import get_vector_store


_cache = get_retriever_cache()
_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = get_vector_store().as_retriever()
    return _retriever


@tool(response_format="content_and_artifact")
def retrieve_pantry_items(
    query: str,
    k: int = 5,
    household_id: UUID | None = None,
) -> Tuple[str, List[Document]]:
    """
    Retrieve relevant pantry items from the Supabase-backed vector store
    to help answer a user query.

    Results are cached per-household and query to avoid redundant vector lookups.
    """
    retriever = _get_retriever()
    household_key = str(household_id) if household_id is not None else "global"

    cached = _cache.get(household_key, query, k)
    if cached is not None:
        return cached

    documents = retriever.get_relevant_documents(query)[:k]
    serialized = "\n\n".join(doc.page_content for doc in documents)
    _cache.set(household_key, query, k, documents, serialized)
    return serialized, documents


retriever_tool = retrieve_pantry_items

