from __future__ import annotations

import json
import logging
from typing import Any

import anyio

from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.contexts.ai.application.prompts import recipes as recipe_prompts
from pantry_server.contexts.ai.application.prompts import shopping_lists as shopping_prompts
from pantry_server.contexts.ai.infrastructure.mock_workflow import MockAiWorkflow
from pantry_server.contexts.ai.infrastructure.providers.gemini import (
    get_gemini_chat,
    get_gemini_embeddings,
)
from pantry_server.core.config import get_settings
from pantry_server.shared.contracts import (
    EmbeddingRequest,
    EmbeddingResult,
    RecipeWorkflowInput,
    RecipeWorkflowOutput,
    ShoppingWorkflowInput,
    ShoppingWorkflowOutput,
)

LOGGER = logging.getLogger("pantry_server.ai.gemini")
GEMINI_CALL_TIMEOUT_SECONDS = 4.0


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

    async def generate_recipe(self, request: RecipeWorkflowInput) -> RecipeWorkflowOutput:
        if self._chat is None:
            return await self._fallback.generate_recipe(request)
        try:
            user_prompt = self._build_recipe_prompt(request)
            with anyio.fail_after(GEMINI_CALL_TIMEOUT_SECONDS):
                response = await anyio.to_thread.run_sync(
                    lambda: self._chat.invoke(
                        [
                            ("system", recipe_prompts.SYSTEM_PROMPT),
                            ("human", user_prompt),
                        ]
                    )
                )
            parsed = self._parse_json_payload(getattr(response, "content", ""))
            recipe = self._normalize_recipe(parsed)
            if recipe is None:
                return await self._fallback.generate_recipe(request)
            return recipe
        except Exception:
            LOGGER.exception("Gemini recipe generation failed; using fallback.")
            return await self._fallback.generate_recipe(request)

    async def generate_shopping_list(
        self,
        request: ShoppingWorkflowInput,
    ) -> ShoppingWorkflowOutput:
        if self._chat is None:
            return await self._fallback.generate_shopping_list(request)
        try:
            user_prompt = shopping_prompts.build_user_message(
                pantry_items=request.pantry_items,
                recipe_goal=request.recipe_goal,
                servings=request.servings,
            )
            with anyio.fail_after(GEMINI_CALL_TIMEOUT_SECONDS):
                response = await anyio.to_thread.run_sync(
                    lambda: self._chat.invoke(
                        [
                            ("system", shopping_prompts.SYSTEM_PROMPT),
                            ("human", user_prompt),
                        ]
                    )
                )
            parsed = self._parse_json_payload(getattr(response, "content", ""))
            shopping_list = self._normalize_shopping_list(parsed)
            if shopping_list is None:
                return await self._fallback.generate_shopping_list(request)
            return shopping_list
        except Exception:
            LOGGER.exception("Gemini shopping list generation failed; using fallback.")
            return await self._fallback.generate_shopping_list(request)

    def _build_recipe_prompt(self, request: RecipeWorkflowInput) -> str:
        encoded_items = ",".join(request.pantry_items) or "none"
        encoded_prefs = ",".join(request.dietary_preferences) or "none"
        return (
            f"pantry_items={encoded_items} "
            f"dietary_preferences={encoded_prefs} "
            "return_one_recipe=true"
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
