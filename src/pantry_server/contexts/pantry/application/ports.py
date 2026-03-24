from typing import Protocol

from pantry_server.contexts.pantry.domain.entities import PantryItem


class PantryRepositoryPort(Protocol):
    async def list_by_household(self, household_id: str) -> list[PantryItem]: ...

    async def create_item(self, item: PantryItem) -> PantryItem: ...
