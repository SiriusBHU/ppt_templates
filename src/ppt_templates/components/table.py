"""表格 / 对比矩阵：原生 PPT 表格。表头深色底，正文行浅色交替，可高亮一列（如推荐方案）。"""

from pptx.enum.text import MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Emu

from ..draw import ALIGN, add_run, emu_box, rgb
from ..errors import PptError
from ..geometry import px_to_emu

NO_STYLE_NO_GRID = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # 去掉内置表格样式，颜色全部由风格 token 决定
CELL_PAD = 12

SCHEMA = {
    "type": "object",
    "required": ["columns", "rows"],
    "properties": {
        "columns": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "rows": {"type": "array", "minItems": 1, "items": {"type": "array", "items": {"type": "string"}}},
        "highlight_column": {"type": "integer", "minimum": 0},
    },
}


def _cell(cell, style, text, text_style, fill, *, color=None, bold=None, align="left"):
    cell.fill.solid()
    cell.fill.fore_color.rgb = rgb(style, fill)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = cell.margin_right = Emu(px_to_emu(CELL_PAD))
    cell.margin_top = cell.margin_bottom = Emu(px_to_emu(CELL_PAD / 2))
    cell.text_frame.word_wrap = True
    p = cell.text_frame.paragraphs[0]
    p.alignment = ALIGN[align]
    add_run(p, style, text, text_style, color, bold)


def _widths(total: float, n: int, first) -> list[float]:
    if first and n > 1:
        return [first] + [(total - first) / (n - 1)] * (n - 1)
    return [total / n] * n


def render(slide, style, box, data, props):
    columns, rows = data["columns"], data["rows"]
    for i, row in enumerate(rows):
        if len(row) != len(columns):
            raise PptError(f"表格第 {i + 1} 行有 {len(row)} 格，表头有 {len(columns)} 列")
    hot = data.get("highlight_column")
    _, _, w, h = box
    shape = slide.shapes.add_table(len(rows) + 1, len(columns), *emu_box(box))
    table = shape.table
    table.first_row = table.horz_banding = False
    table._tbl.tblPr.find(qn("a:tableStyleId")).text = NO_STYLE_NO_GRID
    for col, cw in zip(table.columns, _widths(w, len(columns), props.get("first_column_width"))):
        col.width = Emu(px_to_emu(cw))
    for row in table.rows:
        row.height = Emu(px_to_emu(h / (len(rows) + 1)))

    for c, name in enumerate(columns):
        _cell(table.cell(0, c), style, name, "body_strong", "highlight_strong" if c == hot else "primary",
              color="on_primary", align="left" if c == 0 and c != hot else "center")
    for r, row in enumerate(rows, 1):
        fill = "surface" if r % 2 == 0 else "bg"
        for c, text in enumerate(row):
            if c == hot:
                _cell(table.cell(r, c), style, text, "body", "highlight", color="highlight_strong", bold=True, align="center")
            elif c == 0:
                _cell(table.cell(r, c), style, text, "body_strong", fill)
            else:
                _cell(table.cell(r, c), style, text, "body", fill, align="center")
    return shape
