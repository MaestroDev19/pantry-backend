from datetime import date

from pydantic import BaseModel


class PantryItem(BaseModel):
    id: str
    household_id: str
    name: str
    category: str
    quantity: float
    unit: str
    expiry_date: date | None = None
