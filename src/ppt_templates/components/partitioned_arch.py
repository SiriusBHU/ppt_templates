"""分区架构图：几个竖向分区并排，每个分区顶部是页签、下面按层排模块；可选的共享层横跨所有分区；高亮模块 + 可选图例。"""

import re

from ..draw import add_shape
from .layered_arch import LEGEND_H, _legend

EM = 16                           # 12 pt 文字（body / body_strong）一个全角字的宽度（px）；字号对所有风格统一，所以可以写死
ASCII_EM = 0.6                    # 英文、数字相对全角字的平均宽度，按偏宽（加粗）估算
LINE_H = EM * 1.25                # 一行文字占的高度，按偏保守的行距估算
LABEL_W, LABEL_GAP = 56, 6        # 层名标签的宽度，以及它和模块区之间的间距
HEADER_H, HEADER_GAP = 28, 4      # 分区页签的高度，以及它和分区主体之间的间距
PART_GAP, REGION_GAP = 10, 8      # 分区之间的间距；分区主体与共享层之间的间距
ROW_GAP, PAD, MODULE_GAP = 8, 8, 8
INSET = {"header": 4, "label": 2, "module": 4}  # 各种形状里的文字内边距（px）

_LAYER = {
    "type": "object",
    "required": ["name", "modules"],
    "properties": {
        "name": {"type": "string"},
        "modules": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {"name": {"type": "string"}, "highlight": {"type": "boolean"}},
            },
        },
    },
}

SCHEMA = {
    "type": "object",
    "required": ["partitions"],
    "properties": {
        "partitions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "layers"],
                "properties": {
                    "name": {"type": "string"},
                    "layers": {"type": "array", "minItems": 1, "items": _LAYER},
                },
            },
        },
        "shared": {"type": "array", "items": _LAYER},
    },
}

PROPS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"legend": {"type": "string"}},
}


def _has_highlight(data) -> bool:
    layers = [layer for p in data["partitions"] for layer in p["layers"]] + data.get("shared", [])
    return any(m.get("highlight") for layer in layers for m in layer["modules"])


def _lines(text: str, width: float) -> int:
    """估算 text 在 width 宽的框里折成几行：逐字累加宽度（全角字 1 em，其余 0.6 em），超出就折行。"""
    lines, used = 1, 0.0
    for c in text:
        w = EM if ord(c) > 0x2E7F else EM * ASCII_EM
        if used and used + w > width:
            lines, used = lines + 1, 0.0
        used += w
    return lines


def _inset_x(kind: str, text: str, width: float) -> float:
    """文字左右的内边距。纯中文的文字要折成多行时，把边距加到刚好放下「每行平均字数」个字，
    让 PowerPoint 自己折出各行等长的样子（末行不会只剩一个字）；含英文或数字的保持默认，按单词折。"""
    base = INSET[kind]
    lines = _lines(text, width - 2 * base)
    if lines == 1 or any(ord(c) <= 0x2E7F for c in text):
        return base
    per_line = -(-len(text) // lines)
    return max(base, (width - per_line * EM - 4) / 2)


def _rows(out: list, prefix: tuple, box, layers) -> None:
    """在 box（分区主体或共享层区域）里按层均分高度：左边层名，右边的模块平分剩余宽度。"""
    x, y, w, h = box
    n = len(layers)
    row_h = (h - 2 * PAD - ROW_GAP * (n - 1)) / n
    mx = x + PAD + LABEL_W + LABEL_GAP
    area_w = w - 2 * PAD - LABEL_W - LABEL_GAP
    for j, layer in enumerate(layers):
        ry = y + PAD + j * (row_h + ROW_GAP)
        out.append(("label", (*prefix, j, "name"), (x + PAD, ry, LABEL_W, row_h), layer["name"], False))
        modules = layer["modules"]
        mw = (area_w - MODULE_GAP * (len(modules) - 1)) / len(modules)
        for k, module in enumerate(modules):
            out.append(("module", (*prefix, j, "modules", k, "name"), (mx + k * (mw + MODULE_GAP), ry, mw, row_h),
                        module["name"], module.get("highlight", False)))


def _plan(data, box, legend: bool) -> list:
    """把 box 划成要画的块：(种类, 数据路径, (x, y, w, h), 文字, 是否高亮)，种类 body / header / label / module。
    先画的在前（主体在层名和模块之下）。check 和 render 共用这一份，保证检查的就是画出来的。

    分区宽度：固定开销（内边距 + 层名标签）之外，剩下的宽度按各分区「每层最多的模块数」分配，所以模块少的分区更窄。
    高度：页签之下，分区主体和共享层按总行数均分；层数较少的分区把自己的主体高度均分给自己的层。"""
    x, y, w, h = box
    parts, shared = data["partitions"], data.get("shared", [])
    if legend:
        h -= LEGEND_H
    longest = max(len(p["layers"]) for p in parts)
    regions = 1 + bool(shared)
    avail = h - HEADER_H - HEADER_GAP - 2 * PAD * regions - REGION_GAP * bool(shared)
    unit = (avail - ROW_GAP * (longest - 1 + max(len(shared) - 1, 0))) / (longest + len(shared))
    body_h = longest * unit + ROW_GAP * (longest - 1) + 2 * PAD
    body_y = y + HEADER_H + HEADER_GAP

    widest = [max(len(layer["modules"]) for layer in p["layers"]) for p in parts]
    overhead = 2 * PAD + LABEL_W + LABEL_GAP
    slot = (w - PART_GAP * (len(parts) - 1) - overhead * len(parts) - MODULE_GAP * sum(k - 1 for k in widest)) / sum(widest)

    out, px = [], x
    for i, (part, k) in enumerate(zip(parts, widest)):
        pw = overhead + k * slot + MODULE_GAP * (k - 1)
        out.append(("header", ("partitions", i, "name"), (px, y, pw, HEADER_H), part["name"], False))
        out.append(("body", None, (px, body_y, pw, body_h), None, False))
        _rows(out, ("partitions", i, "layers"), (px, body_y, pw, body_h), part["layers"])
        px += pw + PART_GAP
    if shared:
        shared_h = len(shared) * unit + ROW_GAP * (len(shared) - 1) + 2 * PAD
        region = (x, body_y + body_h + REGION_GAP, w, shared_h)
        out.append(("body", None, region, None, False))
        _rows(out, ("shared",), region, shared)
    return out


def check(data, box) -> list[tuple[tuple, str]]:
    """页签和每个层名、模块名都要放得进自己的框（按字数估算行数），英文单词不能比框宽（否则会被拦腰折断）。
    图例是否预留取决于 props，这里拿不到，所以只要有高亮模块就按预留图例的高度检查，只会更严。"""
    problems = []
    for kind, path, (_, _, w, h), text, _ in _plan(data, box, _has_highlight(data)):
        if kind == "body":
            continue
        avail = w - 2 * INSET[kind]
        lines = _lines(text, avail)
        room = int(h // LINE_H)
        word = max(re.findall(r"[\x21-\x7e]+", text), key=len, default="")
        if len(word) * EM * ASCII_EM > avail:
            problems.append((path, f"英文单词「{word}」比 {w:.0f} px 宽的框还宽，会被拦腰折断，请换短一点的写法，或减少分区 / 模块数"))
        elif avail < EM or lines > room:
            problems.append((path, f"「{text}」在 {w:.0f}×{h:.0f} px 的框里估算要 {lines} 行，只放得下 {max(room, 0)} 行，"
                                   f"请缩短文字，或减少分区 / 层 / 模块数"))
    return problems


def render(slide, style, box, data, props):
    legend = props.get("legend") if _has_highlight(data) else None
    if legend:
        x, y, w, h = box
        _legend(slide, style, (x, y + h - LEGEND_H, w, LEGEND_H), legend)
    for kind, _, b, text, hot in _plan(data, box, bool(legend)):
        if kind == "body":
            add_shape(slide, style, b, "surface")
            continue
        text_opts = dict(text=text, align="center", valign="middle", inset=(_inset_x(kind, text, b[2]), INSET[kind]))
        if kind == "header":
            add_shape(slide, style, b, "bg", line="primary", line_width=1, text_style="body_strong", color="primary", **text_opts)
        elif kind == "label":
            add_shape(slide, style, b, "primary", text_style="body_strong", color="on_primary", **text_opts)
        else:
            add_shape(slide, style, b, "highlight" if hot else "bg",
                      line="highlight_strong" if hot else "line", line_width=1.5 if hot else 0.75,
                      text_style="body_strong", color="highlight_strong" if hot else None, **text_opts)
