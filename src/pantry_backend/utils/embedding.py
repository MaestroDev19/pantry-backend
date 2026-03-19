from __future__ import annotations

from functools import lru_cache

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from pantry_backend.core.settings import get_settings


@lru_cache(maxsize=1)
def embeddings_client() -> GoogleGenerativeAIEmbeddings:
    settings = get_settings()
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embeddings_model,
        api_key=settings.google_genai_api_key,
        output_dimensionality=settings.gemini_embeddings_output_dimensionality,
    )


__all__ = ["embeddings_client"]

