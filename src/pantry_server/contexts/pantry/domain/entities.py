from datetime import date

from pydantic import BaseModel


class PantryItem(BaseModel):
    id: str
    household_id: str
    owner_id: str | None = None
    owner_name: str | None = None
    name: str
    category: str
    quantity: float
    expiry_date: date | None = None
