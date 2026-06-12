from __future__ import annotations

from langchain_community.vectorstores import SupabaseVectorStore

from pantry_server.contexts.ai.infrastructure.providers.gemini import get_gemini_embeddings
from pantry_server.core.config import get_settings
from pantry_server.core.exceptions import AppError
from pantry_server.shared.dependencies import get_supabase_client


from typing import Any, Dict, List, Optional, Tuple
from langchain_core.documents import Document

class CompatibleSupabaseVectorStore(SupabaseVectorStore):
    """
    Subclass of SupabaseVectorStore that supports newer postgrest/supabase-py 
    versions where request builders do not have a mutable `.params` attribute.
    """
    def similarity_search_by_vector_with_relevance_scores(
        self,
        query: List[float],
        k: int,
        filter: Optional[Dict[str, Any]] = None,
        postgrest_filter: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Tuple[Document, float]]:
        # Convert MongoDB-style filter to PostgreSQL syntax if needed
        if filter:
            for key, value in filter.items():
                if isinstance(value, dict) and "$in" in value:
                    in_values = value["$in"]
                    values_str = ",".join(f"'{str(v)}'" for v in in_values)
                    new_filter = f"metadata->>{key} IN ({values_str})"
                    if postgrest_filter:
                        postgrest_filter = f"({postgrest_filter}) and ({new_filter})"
                    else:
                        postgrest_filter = new_filter

        match_documents_params = self.match_args(query, filter)
        query_builder = self._client.rpc(self.query_name, match_documents_params)

        if postgrest_filter:
            if hasattr(query_builder, "params") and hasattr(query_builder.params, "set"):
                query_builder.params = query_builder.params.set(
                    "and", f"({postgrest_filter})"
                )
            else:
                query_builder = query_builder.filter("and", "and", f"({postgrest_filter})")

        if hasattr(query_builder, "params") and hasattr(query_builder.params, "set"):
            query_builder.params = query_builder.params.set("limit", k)
        else:
            query_builder = query_builder.limit(k)

        res = query_builder.execute()

        match_result = [
            (
                Document(
                    metadata=search.get("metadata", {}),
                    page_content=search.get("content", ""),
                ),
                search.get("similarity", 0.0),
            )
            for search in res.data
            if search.get("content")
        ]

        if score_threshold is not None:
            match_result = [
                (doc, similarity)
                for doc, similarity in match_result
                if similarity >= score_threshold
            ]

        return match_result


async def get_vector_store() -> SupabaseVectorStore:
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

    return CompatibleSupabaseVectorStore(
        client=supabase,
        embedding=embeddings,
        table_name="pantry_items",
        query_name="match_pantry_items",
    )



