"""坐标换算：逻辑像素 ↔ EMU、百分比表达式、grid 单元格。"""

import math
import re
from dataclasses import dataclass

CANVAS_W, CANVAS_H = 1280, 720
REF_W, REF_H = 1216, 560  # frame: standard 的参考 body 尺寸
EMU_PER_PX = 9525

Box = tuple[float, float, float, float]

_EXPR = re.compile(r"^\s*(-?\d+(?:\.\d+)?)%\s*(?:([+-])\s*(\d+(?:\.\d+)?))?\s*$")


def px_to_emu(px: float) -> int:
    return round(px * EMU_PER_PX)


def parse_expr(value: int | float | str, total: float) -> float:
    """数字原样返回；"N%"、"N%+M"、"N%-M" 按 total 的百分比加减像素。"""
    if isinstance(value, (int, float)):
        return float(value)
    m = _EXPR.match(value)
    if not m:
        raise ValueError(f"无法解析坐标表达式: {value!r}")
    result = total * float(m[1]) / 100
    if m[2]:
        result += float(m[3]) * (1 if m[2] == "+" else -1)
    return result


def resolve_box(box: list, parent_w: float, parent_h: float) -> Box:
    """box 的 x/w 按父区域宽、y/h 按父区域高解析，结果相对父区域左上角。"""
    x, y, w, h = box
    return (
        parse_expr(x, parent_w),
        parse_expr(y, parent_h),
        parse_expr(w, parent_w),
        parse_expr(h, parent_h),
    )


def grid_cells(box: Box, columns: int, gap: float, count: int) -> list[Box]:
    """列数固定为 columns，行数 = ceil(count / columns)，按行优先返回各单元格。"""
    if count == 0:
        return []
    x, y, w, h = box
    rows = math.ceil(count / columns)
    cw = (w - gap * (columns - 1)) / columns
    ch = (h - gap * (rows - 1)) / rows
    return [(x + (i % columns) * (cw + gap), y + (i // columns) * (ch + gap), cw, ch) for i in range(count)]


@dataclass(frozen=True)
class Transform:
    """参考坐标 → 画布坐标：先逐轴缩放，再平移到 (ox, oy)。"""

    ox: float = 0
    oy: float = 0
    sx: float = 1
    sy: float = 1

    def __call__(self, box: Box) -> Box:
        x, y, w, h = box
        return (self.ox + x * self.sx, self.oy + y * self.sy, w * self.sx, h * self.sy)
