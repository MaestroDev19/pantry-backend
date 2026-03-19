from __future__ import annotations

from langchain_community.vectorstores import SupabaseVectorStore

from pantry_backend.core.exceptions import AppError
from pantry_backend.core.settings import get_settings
from pantry_backend.integrations.gemini_client import get_gemini_embeddings
from pantry_backend.integrations.supabase_client import get_supabase_client


def get_vector_store() -> SupabaseVectorStore:
    """
    Construct a Supabase-backed vector store for pantry embeddings.
    """
    settings = get_settings()

    supabase = get_supabase_client(settings)
    if supabase is None:
        raise AppError(
            "Supabase is not configured for vector store",
            status_code=500,
        )

    embeddings = get_gemini_embeddings(settings)
    if embeddings is None:
        raise AppError(
            "Gemini embeddings are not configured",
            status_code=500,
        )

    return SupabaseVectorStore(
        client=supabase,
        embedding=embeddings,
        table_name="pantry_embeddings",
        query_name="match_pantry_items",
    )

