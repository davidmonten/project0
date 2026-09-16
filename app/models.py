"""Data models shared across the layout engine and the API."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PageMode(str, Enum):
    SHEET = "sheet"  # fixed-size label, e.g. 100x150mm die-cut
    ROLL = "roll"     # continuous roll, height grows to fit content


class PageSize(BaseModel):
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)
    mode: PageMode = PageMode.SHEET


class CardSize(BaseModel):
    width_mm: float = Field(gt=0)
    height_mm: float = Field(gt=0)


class LayoutOptions(BaseModel):
    margin_mm: float = Field(default=2.0, ge=0)
    gutter_mm: float = Field(default=2.0, ge=0)
    allow_rotation: bool = True


class SourceItem(BaseModel):
    id: str
    filename: str
    kind: str  # "pdf" | "image"
    page_count: int = 1
    detected_width_mm: Optional[float] = None
    detected_height_mm: Optional[float] = None
    copies: int = 1


class Placement(BaseModel):
    item_id: str
    item_page: int  # which page of the source item (for multi-page PDFs)
    col: int
    row: int
    rotated: bool


class PageLayout(BaseModel):
    page_index: int
    width_mm: float
    height_mm: float
    cols: int
    rows: int
    cell_width_mm: float
    cell_height_mm: float
    placements: list[Placement]


class LayoutResult(BaseModel):
    cols: int
    rows: int
    cell_width_mm: float
    cell_height_mm: float
    rotated: bool
    slots_per_page: int
    pages: list[PageLayout]
    total_cards: int
    wasted_area_pct: float
