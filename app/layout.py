"""Grid-packing layout engine.

v1 packs a single uniform card size onto a page/label as densely as
possible, trying both orientations of the card against the page and
picking whichever wastes less paper. Multi-size bin-packing is a
possible v2 improvement (see README roadmap) but a uniform grid already
covers the dominant use case (many copies of same-size cards).
"""
from __future__ import annotations

import math

from app.models import (
    CardSize,
    LayoutOptions,
    LayoutResult,
    PageLayout,
    PageMode,
    PageSize,
    Placement,
    SourceItem,
)


def _cols_that_fit(usable_mm: float, cell_mm: float, gutter_mm: float) -> int:
    if cell_mm <= 0 or usable_mm < cell_mm:
        return 0
    return int(math.floor((usable_mm + gutter_mm) / (cell_mm + gutter_mm)))


def _candidate_orientations(card: CardSize, allow_rotation: bool):
    orientations = [(card.width_mm, card.height_mm, False)]
    if allow_rotation and card.width_mm != card.height_mm:
        orientations.append((card.height_mm, card.width_mm, True))
    return orientations


def compute_layout(
    page: PageSize,
    card: CardSize,
    opts: LayoutOptions,
    items: list[SourceItem],
) -> LayoutResult:
    usable_w = page.width_mm - 2 * opts.margin_mm
    usable_h = page.height_mm - 2 * opts.margin_mm
    if usable_w <= 0:
        raise ValueError("Margini troppo larghi per la larghezza pagina")
    if page.mode == PageMode.SHEET and usable_h <= 0:
        raise ValueError("Margini troppo larghi per l'altezza pagina")

    best = None  # (score, cols, rows_per_page, cell_w, cell_h, rotated)
    for cell_w, cell_h, rotated in _candidate_orientations(card, opts.allow_rotation):
        cols = _cols_that_fit(usable_w, cell_w, opts.gutter_mm)
        if cols == 0:
            continue
        if page.mode == PageMode.SHEET:
            rows = _cols_that_fit(usable_h, cell_h, opts.gutter_mm)
            if rows == 0:
                continue
            score = cols * rows
        else:  # ROLL: height grows to fit, so only width packing matters
            rows = None
            score = cols
        candidate = (score, cols, rows, cell_w, cell_h, rotated)
        if best is None or candidate[0] > best[0]:
            best = candidate

    if best is None:
        raise ValueError(
            "La carta non entra nella pagina con questi margini/rotazione"
        )

    _, cols, rows, cell_w, cell_h, rotated = best

    # Expand items into a flat list of (item_id, item_page) units to place,
    # respecting each item's `copies` and multi-page PDFs.
    units: list[tuple[str, int]] = []
    for item in items:
        for _ in range(max(item.copies, 1)):
            for page_no in range(item.page_count):
                units.append((item.id, page_no))
    total_cards = len(units)

    pages: list[PageLayout] = []
    if page.mode == PageMode.SHEET:
        slots_per_page = cols * rows
        n_pages = max(1, math.ceil(total_cards / slots_per_page)) if slots_per_page else 1
        idx = 0
        for p in range(n_pages):
            placements = []
            for r in range(rows):
                for c in range(cols):
                    if idx >= total_cards:
                        break
                    item_id, item_page = units[idx]
                    placements.append(
                        Placement(item_id=item_id, item_page=item_page, col=c, row=r, rotated=rotated)
                    )
                    idx += 1
            pages.append(
                PageLayout(
                    page_index=p,
                    width_mm=page.width_mm,
                    height_mm=page.height_mm,
                    cols=cols,
                    rows=rows,
                    cell_width_mm=cell_w,
                    cell_height_mm=cell_h,
                    placements=placements,
                )
            )
        printed_area = total_cards * card.width_mm * card.height_mm
        used_area = n_pages * page.width_mm * page.height_mm
        wasted_pct = 0.0 if used_area == 0 else max(0.0, 100.0 * (1 - printed_area / used_area))
    else:  # ROLL
        rows = max(1, math.ceil(total_cards / cols)) if total_cards else 1
        height_mm = rows * cell_h + (rows - 1) * opts.gutter_mm + 2 * opts.margin_mm
        placements = []
        idx = 0
        for r in range(rows):
            for c in range(cols):
                if idx >= total_cards:
                    break
                item_id, item_page = units[idx]
                placements.append(
                    Placement(item_id=item_id, item_page=item_page, col=c, row=r, rotated=rotated)
                )
                idx += 1
        pages.append(
            PageLayout(
                page_index=0,
                width_mm=page.width_mm,
                height_mm=height_mm,
                cols=cols,
                rows=rows,
                cell_width_mm=cell_w,
                cell_height_mm=cell_h,
                placements=placements,
            )
        )
        printed_area = total_cards * card.width_mm * card.height_mm
        used_area = page.width_mm * height_mm
        wasted_pct = 0.0 if used_area == 0 else max(0.0, 100.0 * (1 - printed_area / used_area))
        slots_per_page = cols * rows

    return LayoutResult(
        cols=cols,
        rows=rows if page.mode == PageMode.SHEET else pages[0].rows,
        cell_width_mm=cell_w,
        cell_height_mm=cell_h,
        rotated=rotated,
        slots_per_page=slots_per_page,
        pages=pages,
        total_cards=total_cards,
        wasted_area_pct=round(wasted_pct, 1),
    )
