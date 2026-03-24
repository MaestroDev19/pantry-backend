from fastapi import APIRouter

from pantry_server.contexts.ai.presentation.router import router as ai_router
from pantry_server.contexts.households.presentation.router import router as households_router
from pantry_server.contexts.pantry.presentation.router import router as pantry_router
from pantry_server.contexts.recipes.presentation.router import router as recipes_router
from pantry_server.contexts.shopping.presentation.router import router as shopping_router

api_router = APIRouter()
api_router.include_router(pantry_router, prefix="/pantry-items", tags=["pantry"])
api_router.include_router(recipes_router, prefix="/recipes", tags=["recipes"])
api_router.include_router(shopping_router, prefix="/shopping-lists", tags=["shopping"])
api_router.include_router(households_router, prefix="/households", tags=["households"])
api_router.include_router(ai_router, prefix="/ai", tags=["ai"])
