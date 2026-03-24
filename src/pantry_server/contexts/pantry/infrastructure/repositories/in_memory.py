from pantry_server.contexts.pantry.domain.entities import PantryItem


class InMemoryPantryRepository:
    def __init__(self) -> None:
        self._items: dict[str, list[PantryItem]] = {}

    async def list_by_household(self, household_id: str) -> list[PantryItem]:
        return self._items.get(household_id, [])

    async def create_item(self, item: PantryItem) -> PantryItem:
        self._items.setdefault(item.household_id, []).append(item)
        return item
