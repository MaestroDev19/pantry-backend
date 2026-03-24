from uuid import uuid4

from pantry_server.contexts.pantry.application.ports import PantryRepositoryPort
from pantry_server.contexts.pantry.domain.entities import PantryItem


class PantryUseCases:
    def __init__(self, repository: PantryRepositoryPort) -> None:
        self.repository = repository

    async def list_items(self, household_id: str) -> list[PantryItem]:
        return await self.repository.list_by_household(household_id)

    async def add_item(
        self,
        household_id: str,
        name: str,
        category: str,
        quantity: float,
        unit: str,
    ) -> PantryItem:
        item = PantryItem(
            id=str(uuid4()),
            household_id=household_id,
            name=name,
            category=category,
            quantity=quantity,
            unit=unit,
        )
        return await self.repository.create_item(item)
