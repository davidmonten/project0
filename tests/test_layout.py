import pytest

from app.layout import compute_layout
from app.models import CardSize, LayoutOptions, PageMode, PageSize, SourceItem


def make_item(item_id="a", copies=1, page_count=1):
    return SourceItem(id=item_id, filename=f"{item_id}.pdf", kind="pdf", page_count=page_count, copies=copies)


def test_grid_fits_expected_columns_and_rows():
    # 100x150mm label, 63x88mm card (poker size), 2mm margin, 2mm gutter.
    # usable width = 96mm -> 1 column of 63mm (2nd would need 63+2=65 more, total 130 > 96)
    # usable height = 146mm -> floor((146+2)/(88+2)) = floor(148/90) = 1 row
    page = PageSize(width_mm=100, height_mm=150, mode=PageMode.SHEET)
    card = CardSize(width_mm=63, height_mm=88)
    opts = LayoutOptions(margin_mm=2, gutter_mm=2, allow_rotation=False)
    result = compute_layout(page, card, opts, [make_item(copies=1)])
    assert result.cols == 1
    assert result.rows == 1
    assert result.total_cards == 1
    assert len(result.pages) == 1


def test_grid_packs_multiple_small_cards_per_sheet():
    # A4 sheet, small 40x60mm cards, no gutter/margin for simplicity.
    page = PageSize(width_mm=210, height_mm=297, mode=PageMode.SHEET)
    card = CardSize(width_mm=40, height_mm=60)
    opts = LayoutOptions(margin_mm=0, gutter_mm=0, allow_rotation=False)
    result = compute_layout(page, card, opts, [make_item(copies=20)])
    # cols = floor(210/40) = 5, rows = floor(297/60) = 4 -> 20 slots/page
    assert result.cols == 5
    assert result.rows == 4
    assert result.slots_per_page == 20
    assert len(result.pages) == 1  # exactly fits in one page
    assert result.total_cards == 20


def test_grid_paginates_when_more_cards_than_fit():
    page = PageSize(width_mm=210, height_mm=297, mode=PageMode.SHEET)
    card = CardSize(width_mm=40, height_mm=60)
    opts = LayoutOptions(margin_mm=0, gutter_mm=0, allow_rotation=False)
    result = compute_layout(page, card, opts, [make_item(copies=25)])
    assert result.slots_per_page == 20
    assert len(result.pages) == 2
    assert len(result.pages[0].placements) == 20
    assert len(result.pages[1].placements) == 5


def test_rotation_chosen_when_it_fits_more_cards():
    # 100x150mm label (usable 96x146 after 2mm margins), 70x45mm landscape card.
    # Unrotated (70x45): cols=floor(98/72)=1, rows=floor(148/47)=3 -> 3 cards.
    # Rotated (45x70):   cols=floor(98/47)=2, rows=floor(148/72)=2 -> 4 cards, wins.
    page = PageSize(width_mm=100, height_mm=150, mode=PageMode.SHEET)
    card = CardSize(width_mm=70, height_mm=45)
    opts = LayoutOptions(margin_mm=2, gutter_mm=2, allow_rotation=True)
    result = compute_layout(page, card, opts, [make_item(copies=4)])
    assert result.rotated is True
    assert result.cols == 2
    assert result.rows == 2


def test_roll_mode_grows_page_height_to_fit_all_cards():
    page = PageSize(width_mm=100, height_mm=1, mode=PageMode.ROLL)
    card = CardSize(width_mm=40, height_mm=40)
    opts = LayoutOptions(margin_mm=0, gutter_mm=0, allow_rotation=False)
    result = compute_layout(page, card, opts, [make_item(copies=5)])
    assert result.cols == 2  # floor(100/40) = 2
    assert len(result.pages) == 1
    page_layout = result.pages[0]
    assert page_layout.rows == 3  # ceil(5/2)
    assert page_layout.height_mm == pytest.approx(3 * 40)
    assert result.total_cards == 5


def test_multiple_items_with_copies_and_multipage_are_flattened():
    items = [make_item("a", copies=2), make_item("b", copies=1, page_count=2)]
    page = PageSize(width_mm=210, height_mm=297, mode=PageMode.SHEET)
    card = CardSize(width_mm=40, height_mm=60)
    opts = LayoutOptions(margin_mm=0, gutter_mm=0, allow_rotation=False)
    result = compute_layout(page, card, opts, items)
    # 2 copies of "a" (1 page each) + 1 copy of "b" (2 pages) = 4 units
    assert result.total_cards == 4


def test_card_larger_than_page_raises():
    page = PageSize(width_mm=100, height_mm=150, mode=PageMode.SHEET)
    card = CardSize(width_mm=200, height_mm=200)
    opts = LayoutOptions(margin_mm=2, gutter_mm=2, allow_rotation=False)
    with pytest.raises(ValueError):
        compute_layout(page, card, opts, [make_item()])
