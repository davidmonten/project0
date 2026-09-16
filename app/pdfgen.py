"""PDF composition and preview rendering, built on PyMuPDF (fitz).

Takes the abstract layout computed by app.layout and turns it into an
actual print-ready PDF (one page per label/sheet, cards placed in their
grid cells) plus PNG previews for the web UI.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf as fitz
from PIL import Image

from app.models import LayoutOptions, LayoutResult, PageLayout, SourceItem

MM_TO_PT = 72.0 / 25.4
PREVIEW_DPI = 150


def mm_to_pt(mm: float) -> float:
    return mm * MM_TO_PT


def inspect_source(path: Path, kind: str) -> tuple[int, float | None, float | None]:
    """Return (page_count, width_mm, height_mm) for a source file.

    For PDFs the size is read exactly from the first page's mediabox.
    For images we don't know the intended physical size (no reliable
    DPI in most exported card images), so the caller must supply it.
    """
    if kind == "pdf":
        doc = fitz.open(path)
        rect = doc[0].rect
        width_mm = rect.width / MM_TO_PT
        height_mm = rect.height / MM_TO_PT
        page_count = doc.page_count
        doc.close()
        return page_count, width_mm, height_mm
    else:
        with Image.open(path) as im:
            dpi = im.info.get("dpi")
        if dpi and dpi[0]:
            w_px, h_px = Image.open(path).size
            return 1, w_px / dpi[0] * 25.4, h_px / dpi[1] * 25.4
        return 1, None, None


def _place_item(
    dst_page: fitz.Page,
    rect: fitz.Rect,
    item: SourceItem,
    item_page: int,
    rotated: bool,
    source_paths: dict[str, Path],
):
    path = source_paths[item.id]
    rotate = 90 if rotated else 0
    if item.kind == "pdf":
        with fitz.open(path) as src:
            dst_page.show_pdf_page(rect, src, item_page, rotate=rotate)
    else:
        dst_page.insert_image(rect, filename=str(path), rotate=rotate)


def render_output_pdf(
    out_path: Path,
    layout: LayoutResult,
    items: list[SourceItem],
    opts: LayoutOptions,
    source_paths: dict[str, Path],
) -> Path:
    items_by_id = {item.id: item for item in items}
    doc = fitz.open()
    for page in layout.pages:
        _render_page(doc, page, opts, items_by_id, source_paths)
    doc.save(out_path)
    doc.close()
    return out_path


def _render_page(
    doc: fitz.Document,
    page: PageLayout,
    opts: LayoutOptions,
    items_by_id: dict[str, SourceItem],
    source_paths: dict[str, Path],
):
    pdf_page = doc.new_page(width=mm_to_pt(page.width_mm), height=mm_to_pt(page.height_mm))
    for placement in page.placements:
        x0 = opts.margin_mm + placement.col * (page.cell_width_mm + opts.gutter_mm)
        y0 = opts.margin_mm + placement.row * (page.cell_height_mm + opts.gutter_mm)
        rect = fitz.Rect(
            mm_to_pt(x0),
            mm_to_pt(y0),
            mm_to_pt(x0 + page.cell_width_mm),
            mm_to_pt(y0 + page.cell_height_mm),
        )
        item = items_by_id[placement.item_id]
        _place_item(pdf_page, rect, item, placement.item_page, placement.rotated, source_paths)


def render_previews(pdf_path: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    previews = []
    doc = fitz.open(pdf_path)
    zoom = PREVIEW_DPI / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=matrix)
        out_file = out_dir / f"preview_{i}.png"
        pix.save(out_file)
        previews.append(out_file)
    doc.close()
    return previews
