from __future__ import annotations

from enum import Enum


class CategoryEnum(str, Enum):
    PRODUCE = "produce"
    DAIRY = "dairy"
    MEAT = "meat"
    GRAINS = "grains"
    CANNED = "canned"
    FROZEN = "frozen"
    SNACKS = "snacks"
    BEVERAGES = "beverages"
    SPICES = "spices"
    BAKING = "baking"
    OTHER = "other"


class UnitEnum(str, Enum):
    KILOGRAM = "kilogram"
    GRAM = "gram"
    LITER = "liter"
    MILLILITER = "milliliter"
    CUP = "cup"
    TABLESPOON = "tablespoon"
    TEASPOON = "teaspoon"
    PIECE = "piece"
