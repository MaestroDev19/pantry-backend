from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, TypeVar
from uuid import UUID

import anyio

from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.contexts.ai.application.prompts import recipes as recipe_prompts
from pantry_server.contexts.ai.application.prompts import shopping_lists as shopping_prompts
from pantry_server.contexts.ai.infrastructure.context_retrieval import (
    RECIPE_KNOWLEDGE_BASE,
    SHOPPING_KNOWLEDGE_BASE,
    build_recipe_query,
    build_shopping_query,
    retrieve_context,
)
from pantry_server.contexts.ai.infrastructure.mock_workflow import MockAiWorkflow
from pantry_server.contexts.ai.infrastructure.providers.gemini import (
    get_gemini_chat,
    get_gemini_embeddings,
)
from pantry_server.core.config import get_settings
from pantry_server.shared.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    RecipeGenerationResult,
    RecipeWorkflowInput,
    RecipeWorkflowOutput,
    ShoppingGenerationResult,
    ShoppingWorkflowInput,
    ShoppingWorkflowOutput,
)

LOGGER = logging.getLogger("pantry_server.ai.gemini")
GEMINI_CALL_TIMEOUT_SECONDS = 4.0

TRequest = TypeVar("TRequest")
TOutput = TypeVar("TOutput")
TFallbackResult = TypeVar("TFallbackResult")


class GeminiAiWorkflow(AiWorkflowPort):
    def __init__(self) -> None:
        settings = get_settings()
        self._chat = get_gemini_chat(settings)
        self._embeddings = get_gemini_embeddings(settings)
        self._fallback = MockAiWorkflow()

    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResult:
        if self._embeddings is None:
            return await self._fallback.create_embedding(request)
        try:
            with anyio.fail_after(GEMINI_CALL_TIMEOUT_SECONDS):
                vector = await anyio.to_thread.run_sync(
                    lambda: self._embeddings.embed_query(request.text)
                )
            return EmbeddingResult(vector=vector)
        except Exception:
            LOGGER.exception("Gemini embeddings failed; using fallback.")
            return await self._fallback.create_embedding(request)

    async def generate_recipe(
        self,
        request: RecipeWorkflowInput,
        household_id: UUID | None = None,
    ) -> RecipeGenerationResult:
        return await self._generate_with_gemini(
            request=request,
            query=build_recipe_query(request),
            household_id=household_id,
            fallback_knowledge=RECIPE_KNOWLEDGE_BASE,
            system_prompt=recipe_prompts.SYSTEM_PROMPT,
            build_user_prompt=lambda ctx: self._build_recipe_prompt(request, ctx),
            normalize=self._normalize_recipe,
            fallback=self._fallback.generate_recipe,
            to_result=lambda recipe, ctx: RecipeGenerationResult(
                recipe=recipe,
                retrieved_context=ctx,
            ),
            pick_from_fallback=lambda result: result.recipe,
            merge_context=lambda fallback, ctx: ctx or fallback.retrieved_context,
        )

    async def generate_shopping_list(
        self,
        request: ShoppingWorkflowInput,
        household_id: UUID | None = None,
    ) -> ShoppingGenerationResult:
        return await self._generate_with_gemini(
            request=request,
            query=build_shopping_query(request),
            household_id=household_id,
            fallback_knowledge=SHOPPING_KNOWLEDGE_BASE,
            system_prompt=shopping_prompts.SYSTEM_PROMPT,
            build_user_prompt=lambda ctx: self._build_shopping_prompt(request, ctx),
            normalize=self._normalize_shopping_list,
            fallback=self._fallback.generate_shopping_list,
            to_result=lambda shopping_list, ctx: ShoppingGenerationResult(
                shopping_list=shopping_list,
                retrieved_context=ctx,
            ),
            pick_from_fallback=lambda result: result.shopping_list,
            merge_context=lambda fallback, ctx: ctx or fallback.retrieved_context,
        )

    async def _generate_with_gemini(
        self,
        *,
        request: TRequest,
        query: str,
        household_id: UUID | None = None,
        fallback_knowledge: list[str],
        system_prompt: str,
        build_user_prompt: Callable[[list[str]], str],
        normalize: Callable[[Any], TOutput | None],
        fallback: Callable[[TRequest], Awaitable[TFallbackResult]],
        to_result: Callable[[TOutput, list[str]], Any],
        pick_from_fallback: Callable[[TFallbackResult], TOutput],
        merge_context: Callable[[TFallbackResult, list[str]], list[str]],
    ) -> Any:
        retrieved_context = await retrieve_context(
            query,
            household_id=household_id,
            fallback_knowledge=fallback_knowledge,
        )
        if self._chat is None:
            fallback_result = await fallback(request)
            return to_result(
                pick_from_fallback(fallback_result),
                merge_context(fallback_result, retrieved_context),
            )

        try:
            user_prompt = build_user_prompt(retrieved_context)
            with anyio.fail_after(GEMINI_CALL_TIMEOUT_SECONDS):
                response = await anyio.to_thread.run_sync(
                    lambda: self._chat.invoke(
                        [
                            ("system", system_prompt),
                            ("human", user_prompt),
                        ]
                    )
                )
            parsed = self._parse_json_payload(getattr(response, "content", ""))
            normalized = normalize(parsed)
            if normalized is None:
                fallback_result = await fallback(request)
                return to_result(pick_from_fallback(fallback_result), retrieved_context)
            return to_result(normalized, retrieved_context)
        except Exception:
            LOGGER.exception("Gemini generation failed; using fallback.")
            fallback_result = await fallback(request)
            return to_result(pick_from_fallback(fallback_result), retrieved_context)

    @staticmethod
    def _format_retrieved_context(chunks: Sequence[str]) -> str:
        if not chunks:
            return "none"
        return "\n\n".join(chunks)

    def _build_recipe_prompt(
        self,
        request: RecipeWorkflowInput,
        retrieved_context: list[str],
    ) -> str:
        encoded_items = ",".join(request.pantry_items) or "none"
        encoded_prefs = ",".join(request.dietary_preferences) or "none"
        return (
            f"retrieved_context={self._format_retrieved_context(retrieved_context)} "
            f"pantry_items={encoded_items} "
            f"dietary_preferences={encoded_prefs} "
            "return_one_recipe=true"
        )

    def _build_shopping_prompt(
        self,
        request: ShoppingWorkflowInput,
        retrieved_context: list[str],
    ) -> str:
        base = shopping_prompts.build_user_message(
            pantry_items=request.pantry_items,
            recipe_goal=request.recipe_goal,
            servings=request.servings,
        )
        return (
            f"retrieved_context={self._format_retrieved_context(retrieved_context)} "
            f"{base}"
        )

    @staticmethod
    def _parse_json_payload(content: Any) -> Any:
        if isinstance(content, list):
            content = " ".join(
                str(part.get("text", part)) if isinstance(part, dict) else str(part)
                for part in content
            )
        if not isinstance(content, str):
            return None

        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _normalize_recipe(payload: Any) -> RecipeWorkflowOutput | None:
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if not isinstance(payload, dict):
            return None
        title = str(payload.get("title", "")).strip()
        ingredients = payload.get("ingredients") or payload.get("ing") or []
        instructions = payload.get("instructions") or payload.get("steps") or []
        normalized_ingredients = [str(item) for item in ingredients if str(item).strip()]
        normalized_instructions = [str(step) for step in instructions if str(step).strip()]
        if not title or not normalized_ingredients or not normalized_instructions:
            return None
        return RecipeWorkflowOutput(
            title=title,
            ingredients=normalized_ingredients,
            instructions=normalized_instructions,
        )

    @staticmethod
    def _normalize_shopping_list(payload: Any) -> ShoppingWorkflowOutput | None:
        if not isinstance(payload, dict):
            return None
        raw_items = payload.get("items", [])
        if not isinstance(raw_items, list):
            return None
        normalized_items: list[str] = []
        for item in raw_items:
            if isinstance(item, dict):
                value = item.get("name")
                if value:
                    normalized_items.append(str(value))
            elif str(item).strip():
                normalized_items.append(str(item))
        if not normalized_items:
            return None
        return ShoppingWorkflowOutput(items=normalized_items)
