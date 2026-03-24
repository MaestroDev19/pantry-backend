from __future__ import annotations

from enum import Enum


class CategoryEnum(str, Enum):
    PRODUCE = "produce"
    DAIRY = "dairy"
    MEAT = "meat"
    GRAINS = "grains"
    CANNED = "canned"
    FROZEN = "frozen"
    SPICES = "spices"
    OTHER = "other"


class UnitEnum(str, Enum):
    PIECE = "piece"
    GRAM = "gram"
    KILOGRAM = "kilogram"
    MILLILITER = "milliliter"
    LITER = "liter"
    CUP = "cup"
    TABLESPOON = "tablespoon"
    TEASPOON = "teaspoon"
