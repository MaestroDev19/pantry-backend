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
