"""泳道路线图：顶部时间轴，每条产品线一条泳道，条目按起止时间跨若干列；底部可选一排首尾相接的时代箭头；高亮条目 + 可选图例。"""

import re
from typing import NamedTuple

from ..draw import add_arrow, add_shape, set_paragraphs
from .layered_arch import LEGEND_H, _legend

EM_BODY, EM_DETAIL = 16, 40 / 3   # 12 pt（body / body_strong）、10 pt（detail）一个全角字的宽度（px）；字号对所有风格统一，所以可以写死
ASCII_EM = 0.6                    # 英文、数字相对全角字的平均宽度，按偏宽（加粗）估算
LINE_K = 1.3                      # 行高 = 字宽 × LINE_K：微软雅黑行距偏大，按偏保守的行距估算
LABEL_W, LABEL_GAP = 80, 8        # 泳道名标签的宽度，以及它和时间轴之间的间距
AXIS_H, AXIS_GAP = 26, 4          # 时间轴一行的高度，以及它和第一条泳道之间的间距
LANE_GAP, LANE_TOP, LANE_FOOT = 6, 3, 10   # 泳道之间的间距；条目与泳道上沿的间距；条目之下留给时间箭头的高度
MIN_LANE_H, MAX_LANE_H = 44, 140  # 泳道高度的下限；有富余高度时单条泳道最高长到多少
ERA_GAP, TIP = 10, 14             # 泳道与时代行之间的间距；时代箭头的箭尖深度
COL_GAP, NOTE_GAP = 6, 2          # 相邻条目之间的间距（每侧一半）；条目里名称与备注、备注与备注的间距
INSET = {"period": (4, 2), "label": (2, 2), "item": (6, 3), "era": (TIP + 4, 3)}  # 各种形状里的文字内边距 (左右, 上下)（px）

_ENTRY = {
    "from": {"type": "string"},
    "to": {"type": "string"},
    "highlight": {"type": "boolean"},
}

SCHEMA = {
    "type": "object",
    "required": ["periods", "lanes"],
    "properties": {
        "periods": {"type": "array", "minItems": 1, "uniqueItems": True, "items": {"type": "string"}},
        "lanes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "items"],
                "properties": {
                    "name": {"type": "string"},
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["name", "from"],
                            "properties": {"name": {"type": "string"}, "notes": {"type": "array", "items": {"type": "string"}},
                                           **_ENTRY},
                        },
                    },
                },
            },
        },
        "eras": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "from"],
                "properties": {"name": {"type": "string"}, "note": {"type": "string"}, **_ENTRY},
            },
        },
    },
}

PROPS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"legend": {"type": "string"}},
}


class Block(NamedTuple):
    """一个要画的块：种类 period / label / line / item / era；box；文字 [(数据路径, 文字, 字宽 em)]，第 1 条是名称、其余是备注；是否高亮。"""
    kind: str
    box: tuple
    texts: tuple = ()
    hot: bool = False


def _has_highlight(data) -> bool:
    entries = [item for lane in data["lanes"] for item in lane["items"]] + data.get("eras", [])
    return any(e.get("highlight") for e in entries)


def _lines(text: str, width: float, em: float) -> int:
    """估算 text 在 width 宽的框里折成几行：逐字累加宽度（全角字 1 em，其余 0.6 em），超出就折行。"""
    lines, used = 1, 0.0
    for c in text:
        w = em if ord(c) > 0x2E7F else em * ASCII_EM
        if used and used + w > width:
            lines, used = lines + 1, 0.0
        used += w
    return lines


def _text_h(kind: str, w: float, texts) -> float:
    """名称 + 备注叠在一个 w 宽的框里需要多高（px）。"""
    ix, iy = INSET[kind]
    h = 2 * iy
    for i, (_, text, em) in enumerate(texts):
        h += _lines(text, w - 2 * ix, em) * em * LINE_K + (NOTE_GAP if i else 0)
    return h


def _span(periods, entry) -> tuple[int, int]:
    return periods.index(entry["from"]), periods.index(entry.get("to", entry["from"]))


def _texts(entry, path) -> tuple:
    """条目的名称，加上备注：item 的 notes 数组（逐条）或 era 的单个 note；每项 (数据路径, 文字, 字宽 em)。"""
    out = [((*path, "name"), entry["name"], EM_BODY)]
    out += [((*path, "notes", k), note, EM_DETAIL) for k, note in enumerate(entry.get("notes", []))]
    if entry.get("note"):
        out.append(((*path, "note"), entry["note"], EM_DETAIL))
    return tuple(out)


def _plan(data, box, legend: bool) -> list[Block]:
    """把 box 划成要画的块，先画的在前。check 和 render 共用这一份，保证检查的就是画出来的。

    横向：泳道名标签之后的宽度按 periods 等分成列，条目和时代按 from / to 占若干列，两侧各留 COL_GAP / 2。
    纵向：时间轴一行；每条泳道的高度 = 它里面最高的条目（名称 + 备注的估算行数）+ 上沿间距 + 条目下方的时间箭头，有富余高度时平均分给各泳道
    （单条最高 MAX_LANE_H）；时代行紧跟在最后一条泳道之后。内容多到放不下时照常往下排，由 check 报错。"""
    x, y, w, h = box
    periods, lanes, eras = data["periods"], data["lanes"], data.get("eras", [])
    x0, cw = x + LABEL_W + LABEL_GAP, (w - LABEL_W - LABEL_GAP) / len(periods)

    def cols(entry):  # 条目占的横向范围 (x, 宽)
        a, b = _span(periods, entry)
        return x0 + a * cw + COL_GAP / 2, (b - a + 1) * cw - COL_GAP

    out = [Block("period", (x0 + i * cw + COL_GAP / 2, y, cw - COL_GAP, AXIS_H), ((("periods", i), p, EM_BODY),))
           for i, p in enumerate(periods)]

    item_texts = [[_texts(item, ("lanes", i, "items", j)) for j, item in enumerate(lane["items"])] for i, lane in enumerate(lanes)]
    need = [max(MIN_LANE_H,
                _text_h("label", LABEL_W, ((None, lane["name"], EM_BODY),)),
                *(_text_h("item", cols(item)[1], texts) + LANE_TOP + LANE_FOOT for item, texts in zip(lane["items"], item_texts[i])))
            for i, lane in enumerate(lanes)]
    era_texts = [_texts(era, ("eras", k)) for k, era in enumerate(eras)]
    era_h = max((_text_h("era", cols(era)[1], texts) for era, texts in zip(eras, era_texts)), default=0)

    fixed = AXIS_H + AXIS_GAP + LANE_GAP * (len(lanes) - 1) + (ERA_GAP + era_h if eras else 0) + (LEGEND_H if legend else 0)
    spare = max(h - fixed - sum(need), 0) / len(lanes)
    ly = y + AXIS_H + AXIS_GAP
    for i, lane in enumerate(lanes):
        lh = max(need[i], min(need[i] + spare, MAX_LANE_H))
        out.append(Block("label", (x, ly, LABEL_W, lh), ((("lanes", i, "name"), lane["name"], EM_BODY),)))
        out.append(Block("line", (x0, ly + lh - LANE_FOOT / 2 - 1, cw * len(periods), 0)))
        for item, texts in zip(lane["items"], item_texts[i]):
            ix, iw = cols(item)
            out.append(Block("item", (ix, ly + LANE_TOP, iw, lh - LANE_TOP - LANE_FOOT), texts, item.get("highlight", False)))
        ly += lh + LANE_GAP
    for era, texts in zip(eras, era_texts):
        ex, ew = cols(era)
        out.append(Block("era", (ex, ly - LANE_GAP + ERA_GAP, ew, era_h), texts, era.get("highlight", False)))  # ly 已含最后一个 LANE_GAP
    return out


def _spans(periods, entries, where):
    """各条目的 (起, 止) 列号（出错的是 None），以及 from / to 不在 periods 里、to 早于 from 的问题。"""
    spans, problems = [], []
    for i, entry in enumerate(entries):
        bad = [key for key in ("from", "to") if key in entry and entry[key] not in periods]
        for key in bad:
            problems.append(((*where, i, key), f"「{entry[key]}」不在 periods 里，可选：{'、'.join(periods)}"))
        span = None if bad else _span(periods, entry)
        if span and span[1] < span[0]:
            problems.append(((*where, i, "to"), f"to「{entry['to']}」早于 from「{entry['from']}」"))
            span = None
        spans.append(span)
    return spans, problems


def _overlaps(spans, entries, where):
    return [((*where, j), f"与「{entries[k]['name']}」占用了同一时间段，同一行里的条目不能重叠")
            for j in range(len(spans)) for k in range(j)
            if spans[j] and spans[k] and spans[j][0] <= spans[k][1] and spans[k][0] <= spans[j][1]]


def check(data, box) -> list[tuple[tuple, str]]:
    """from / to 要在 periods 里且 to 不早于 from，同一泳道的条目、时代之间不能重叠；
    时间轴上的标签只能一行，英文单词不能比框宽（否则会被拦腰折断），所有泳道和时代行加起来不能超出 box 的高度。
    图例是否预留取决于 props，这里拿不到，所以只要有高亮就按预留图例的高度检查，只会更严。"""
    periods, lanes, eras = data["periods"], data["lanes"], data.get("eras", [])
    problems, broken = [], False
    groups = [(("lanes", i, "items"), lane["items"]) for i, lane in enumerate(lanes)] + [(("eras",), eras)]
    for path, entries in groups:
        spans, found = _spans(periods, entries, path)
        problems += found + _overlaps(spans, entries, path)
        broken = broken or bool(found)
    if broken:
        return problems  # 起止时间有错，没法排版

    legend = _has_highlight(data)
    blocks = _plan(data, box, legend)
    limit = box[1] + box[3] - (LEGEND_H if legend else 0)
    bottom = max(b.box[1] + b.box[3] for b in blocks)
    if bottom > limit + 0.5:
        problems.append((("lanes",), f"{len(lanes)} 条泳道{'和时代行' if eras else ''}估算要 {bottom - box[1]:.0f} px 高，"
                                     f"只放得下 {limit - box[1]:.0f} px，请减少泳道数 / 备注条数，或缩短文字"))
    for b in blocks:
        avail = b.box[2] - 2 * INSET[b.kind][0] if b.texts else 0
        for path, text, em in b.texts:
            word = max(re.findall(r"[\x21-\x7e]+", text), key=len, default="")
            if len(word) * em * ASCII_EM > avail:
                problems.append((path, f"英文单词「{word}」比 {b.box[2]:.0f} px 宽的框还宽，会被拦腰折断，请换短一点的写法，或减少时间段数"))
            elif b.kind == "period" and (avail < em or _lines(text, avail, em) > 1):
                problems.append((path, f"「{text}」在 {b.box[2]:.0f}×{b.box[3]:.0f} px 的框里估算要 {_lines(text, avail, em)} 行，"
                                       f"只放得下 1 行，请缩短文字，或减少时间段数"))
    return problems


def render(slide, style, box, data, props):
    legend = props.get("legend") if _has_highlight(data) else None
    if legend:
        x, y, w, h = box
        _legend(slide, style, (x, y + h - LEGEND_H, w, LEGEND_H), legend)
    for kind, b, texts, hot in _plan(data, box, bool(legend)):
        x, y, w, h = b
        if kind == "line":
            add_arrow(slide, style, (x, y), (x + w, y), color="muted", width=1)
            continue
        opts = dict(align="center", valign="middle", inset=INSET[kind])
        name = texts[0][1]
        if kind == "period":
            add_shape(slide, style, b, "surface", text=name, text_style="body_strong", color="primary", **opts)
        elif kind == "label":
            add_shape(slide, style, b, "primary", text=name, text_style="body_strong", color="on_primary", **opts)
        else:
            ink = "highlight_strong" if hot else None  # 非重点只靠底色和边框淡化，文字仍用默认的黑色
            paras = [(name, "body_strong", ink, None)] + [(t, "detail", ink, None) for _, t, _ in texts[1:]]
            fill = "highlight" if hot else "surface" if kind == "era" else "bg"
            shape = add_shape(slide, style, b, fill,
                              line="highlight_strong" if hot else "line", line_width=1.5 if hot else 0.75,
                              kind="pentagon" if kind == "era" else "rect")
            if kind == "era":
                shape.adjustments[0] = TIP / min(w, h)
            set_paragraphs(shape.text_frame, style, paras, gap=NOTE_GAP, **opts)
