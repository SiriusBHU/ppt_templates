import pytest

from ppt_templates.geometry import Transform, grid_cells, parse_expr, px_to_emu, resolve_box


def test_px_to_emu():
    assert px_to_emu(1) == 9525
    assert px_to_emu(1280) == 12192000
    assert px_to_emu(720) == 6858000
    assert px_to_emu(2.5) == 23812  # 四舍五入到整数 EMU


@pytest.mark.parametrize(
    "value, total, expected",
    [
        (12, 400, 12),
        (7.5, 400, 7.5),
        ("100%", 390, 390),
        ("50%", 390, 195),
        ("100%-16", 390, 374),
        ("100%+4", 390, 394),
        ("50% - 10", 200, 90),
        ("0%", 200, 0),
    ],
)
def test_parse_expr(value, total, expected):
    assert parse_expr(value, total) == pytest.approx(expected)


def test_parse_expr_rejects_garbage():
    with pytest.raises(ValueError):
        parse_expr("wide", 100)


def test_resolve_box_uses_width_for_x_w_and_height_for_y_h():
    assert resolve_box([16, "50%", "100%-16", "100%-26"], 390, 100) == (16, 50, 374, 74)


def test_grid_cells_single_column():
    # 设计要点：box 390×286，3 项，gap 12 → 单元格高 (286-24)/3
    cells = grid_cells((770, 34, 390, 286), columns=1, gap=12, count=3)
    ch = (286 - 2 * 12) / 3
    assert cells == [(770, 34 + i * (ch + 12), 390, ch) for i in range(3)]


def test_grid_cells_rows_and_columns():
    # 5 项 3 列 → 2 行；末行只有 2 个单元格，宽度仍按 3 列计算
    cells = grid_cells((0, 0, 366, 130), columns=3, gap=12, count=5)
    cw, ch = (366 - 24) / 3, (130 - 12) / 2
    assert len(cells) == 5
    assert cells[0] == (0, 0, cw, ch)
    assert cells[2] == (2 * (cw + 12), 0, cw, ch)
    assert cells[3] == (0, ch + 12, cw, ch)


def test_grid_cells_empty():
    assert grid_cells((0, 0, 100, 100), columns=3, gap=10, count=0) == []


def test_transform_scales_per_axis_then_offsets():
    tf = Transform(60, 150, 2, 0.5)
    assert tf((10, 20, 100, 40)) == (80, 160, 200, 20)
