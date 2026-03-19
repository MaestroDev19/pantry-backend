from __future__ import annotations

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from pantry_backend.core.settings import Settings


def get_gemini_chat(settings: Settings) -> ChatGoogleGenerativeAI | None:
    if settings.google_genai_api_key is None:
        return None

    return ChatGoogleGenerativeAI(
        api_key=settings.google_genai_api_key,
        model=settings.gemini_model,
        temperature=settings.gemini_temperature,
        max_output_tokens=settings.gemini_max_tokens,
        max_retries=settings.gemini_max_retries,
    )


def get_gemini_embeddings(settings: Settings) -> GoogleGenerativeAIEmbeddings | None:
    if settings.google_genai_api_key is None:
        return None

    return GoogleGenerativeAIEmbeddings(
        api_key=settings.google_genai_api_key,
        model=settings.gemini_embeddings_model,
        task_type="retrieval_document",
        dimensions=settings.gemini_embeddings_output_dimensionality,
    )

