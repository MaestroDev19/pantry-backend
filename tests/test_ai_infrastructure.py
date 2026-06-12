from types import SimpleNamespace

import anyio
import pytest

from pantry_server.contexts.ai.infrastructure import vector_store
from pantry_server.contexts.ai.infrastructure.mock_workflow import MockAiWorkflow
from pantry_server.contexts.ai.infrastructure.providers import gemini
from pantry_server.core.config import Settings
from pantry_server.core.exceptions import AppError
from pantry_server.shared.contracts import EmbeddingRequest, RecipeWorkflowInput, ShoppingWorkflowInput


def test_mock_ai_workflow_create_embedding_returns_deterministic_vector() -> None:
    workflow = MockAiWorkflow()

    result = anyio.run(workflow.create_embedding, EmbeddingRequest(text="abcd"))

    assert result.vector == [4.0, 2.0, 1.0]


def test_mock_ai_workflow_generate_recipe_uses_request_items_or_defaults() -> None:
    workflow = MockAiWorkflow()

    from_request = anyio.run(
        workflow.generate_recipe,
        RecipeWorkflowInput(pantry_items=["beans"], dietary_preferences=[]),
    )

    assert from_request.recipe.ingredients == ["beans"]
    assert from_request.recipe.title == "Mock Pantry Bowl"
    assert len(from_request.recipe.instructions) == 3
    assert from_request.retrieved_context == []


def test_recipe_workflow_input_rejects_empty_pantry_items() -> None:
    with pytest.raises(ValueError):
        RecipeWorkflowInput(pantry_items=[], dietary_preferences=[])


def test_mock_ai_workflow_generate_shopping_list_returns_sorted_missing_items() -> None:
    workflow = MockAiWorkflow()

    result = anyio.run(
        workflow.generate_shopping_list,
        ShoppingWorkflowInput(pantry_items=["Salt", "garlic"], recipe_goal="simple", servings=2),
    )

    assert result.shopping_list.items == ["olive oil", "pasta", "tomato"]
    assert result.retrieved_context == []


def test_get_gemini_chat_returns_none_when_api_key_missing() -> None:
    settings = Settings()
    settings.google_genai_api_key = None
    assert gemini.get_gemini_chat(settings) is None


def test_get_gemini_chat_constructs_client_with_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pantry_server.contexts.ai.infrastructure.providers.gemini.ChatGoogleGenerativeAI",
        lambda **kwargs: kwargs,
    )
    settings = Settings(
        gemini_model="gemini-test",
        gemini_temperature=0.7,
        gemini_max_tokens=123,
        gemini_max_retries=9,
    )
    settings.google_genai_api_key = "key"

    client = gemini.get_gemini_chat(settings)

    assert client == {
        "api_key": "key",
        "model": "gemini-test",
        "temperature": 0.7,
        "max_output_tokens": 123,
        "max_retries": 9,
    }


def test_get_gemini_embeddings_returns_none_when_api_key_missing() -> None:
    settings = Settings()
    settings.google_genai_api_key = None
    assert gemini.get_gemini_embeddings(settings) is None


def test_get_gemini_embeddings_constructs_client_with_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pantry_server.contexts.ai.infrastructure.providers.gemini.GoogleGenerativeAIEmbeddings",
        lambda **kwargs: kwargs,
    )
    settings = Settings(
        gemini_embeddings_model="embedding-test",
        gemini_embeddings_output_dimensionality=256,
    )
    settings.google_genai_api_key = "key"

    embeddings = gemini.get_gemini_embeddings(settings)

    assert embeddings == {
        "api_key": "key",
        "model": "embedding-test",
        "task_type": "retrieval_document",
        "output_dimensionality": 256,
    }


def test_get_vector_store_raises_when_supabase_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pantry_server.contexts.ai.infrastructure.vector_store.get_settings", lambda: Settings())
    monkeypatch.setattr("pantry_server.contexts.ai.infrastructure.vector_store.get_supabase_client", lambda _: None)

    with pytest.raises(AppError) as exc_info:
        anyio.run(vector_store.get_vector_store)

    assert exc_info.value.message == "Supabase is not configured for vector store"
    assert exc_info.value.status_code == 500


def test_get_vector_store_raises_when_embeddings_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("pantry_server.contexts.ai.infrastructure.vector_store.get_settings", lambda: Settings())
    monkeypatch.setattr(
        "pantry_server.contexts.ai.infrastructure.vector_store.get_supabase_client",
        lambda _: SimpleNamespace(name="supabase"),
    )
    monkeypatch.setattr(
        "pantry_server.contexts.ai.infrastructure.vector_store.get_gemini_embeddings",
        lambda _: None,
    )

    with pytest.raises(AppError) as exc_info:
        anyio.run(vector_store.get_vector_store)

    assert exc_info.value.message == "Gemini embeddings are not configured"
    assert exc_info.value.status_code == 500


def test_get_vector_store_constructs_supabase_vector_store(monkeypatch: pytest.MonkeyPatch) -> None:
    supabase = SimpleNamespace(name="supabase")
    embeddings = SimpleNamespace(name="embeddings")
    monkeypatch.setattr("pantry_server.contexts.ai.infrastructure.vector_store.get_settings", lambda: Settings())
    monkeypatch.setattr(
        "pantry_server.contexts.ai.infrastructure.vector_store.get_supabase_client",
        lambda _: supabase,
    )
    monkeypatch.setattr(
        "pantry_server.contexts.ai.infrastructure.vector_store.get_gemini_embeddings",
        lambda _: embeddings,
    )
    monkeypatch.setattr(
        "pantry_server.contexts.ai.infrastructure.vector_store.CompatibleSupabaseVectorStore",
        lambda **kwargs: kwargs,
    )

    store = anyio.run(vector_store.get_vector_store)

    assert store == {
        "client": supabase,
        "embedding": embeddings,
        "table_name": "pantry_items",
        "query_name": "match_pantry_items",
    }


def test_build_retrieve_context_tool_similarity_search() -> None:
    from pantry_server.contexts.ai.infrastructure.context_retrieval import (
        build_retrieve_context_tool,
    )

    doc = SimpleNamespace(metadata={"id": "item-1"}, page_content="tomato pasta")
    vector_store = SimpleNamespace(
        similarity_search=lambda query, k=2, filter=None: [doc] if query else [],
    )

    tool = build_retrieve_context_tool(vector_store, k=2)
    content = tool.invoke({"query": "tomato"})

    assert "tomato pasta" in content
    assert "item-1" in content


def test_retrieve_context_uses_keyword_fallback_when_vector_store_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pantry_server.contexts.ai.infrastructure import context_retrieval

    async def _raise_app_error():
        raise AppError("Supabase is not configured for vector store", status_code=500)

    monkeypatch.setattr(context_retrieval, "get_vector_store", _raise_app_error)

    chunks = anyio.run(
        lambda: context_retrieval.retrieve_context(
            "tomato pasta",
            k=2,
            fallback_knowledge=context_retrieval.RECIPE_KNOWLEDGE_BASE,
        )
    )

    assert len(chunks) == 2
    assert any("Tomato" in chunk for chunk in chunks)
