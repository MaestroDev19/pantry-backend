from functools import lru_cache

from pantry_server.contexts.ai.application.ports import AiWorkflowPort
from pantry_server.contexts.ai.infrastructure.gemini_workflow import GeminiAiWorkflow


@lru_cache(maxsize=1)
def _gemini_ai_workflow() -> GeminiAiWorkflow:
    return GeminiAiWorkflow()


def get_ai_workflow() -> AiWorkflowPort:
    return _gemini_ai_workflow()
