"""能力地图：可选的总标题；若干分组（灰底面板，顶部是组名），组里的条目按行排成网格；
带 items 的条目是组内的分组框（自带标题和内层网格）；条目按 tag 分两种底色，图例画在底部左侧。"""

import re
from typing import NamedTuple

from ..draw import add_shape, add_text
from .lane_roadmap import ASCII_EM, _lines
from .partitioned_arch import _inset_x

EM, EM_TITLE, EM_DETAIL = 16, 56 / 3, 40 / 3   # 12 / 14 / 10 pt 一个全角字的宽度（px）；字号对所有风格统一，所以可以写死
LINE_H = EM * 1.25                # 条目文字一行占的高度，按偏保守的行距估算
INSET_X, INSET_Y = 4, 3           # 条目里的文字内边距
TITLE_H, TITLE_GAP = 24, 8        # 总标题一行的高度，以及它和第一个分组之间的间距
GROUP_GAP, ROW_GAP, ITEM_GAP, PAD = 8, 8, 8, 8   # 分组之间、行与行、同一行条目之间的间距；分组面板的左右 / 下内边距
SUB_TITLE_H, TITLE_TOP, TITLE_BELOW = 20, 4, 4   # 分组框标题一行的高度；组名 / 分组框标题与面板上沿、与下方条目的间距
GROUP_TOP, SUB_TOP, SUB_BOTTOM = TITLE_TOP + TITLE_H + TITLE_BELOW, TITLE_TOP + SUB_TITLE_H + TITLE_BELOW, 8   # 面板顶部留给组名、分组框顶部留给标题的高度；分组框的下内边距
MIN_ROW_H, MAX_ROW_H = 28, 56     # 一行条目的最低高度；有富余高度时单行最高长到多少
LEGEND_H, LEGEND_GAP = 24, 8      # 图例一行的高度，以及它和分组之间的间距
SWATCH, SWATCH_GAP, ENTRY_GAP = 14, 6, 20   # 图例色块的边长，色块与文字、相邻图例项之间的间距
TITLE_INSET = 4                   # 标题文字的左右内边距
FILLS = ("bg", "highlight")       # legend 的第 1、2 项对应的底色；没写 tag 的条目用第 1 种

_LEAF = {
    "type": "object",
    "required": ["name"],
    "additionalProperties": False,
    "properties": {"name": {"type": "string"}, "tag": {"type": "string"}, "wide": {"type": "boolean"}},
}

SCHEMA = {
    "type": "object",
    "required": ["groups"],
    "properties": {
        "title": {"type": "string"},
        "groups": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["name", "items"],
                "properties": {
                    "name": {"type": "string"},
                    "columns": {"type": "integer", "minimum": 1},
                    "items": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {
                                **_LEAF["properties"],
                                "columns": {"type": "integer", "minimum": 1},
                                "items": {"type": "array", "minItems": 1, "items": _LEAF},
                            },
                        },
                    },
                },
            },
        },
        "legend": {
            "type": "array",
            "maxItems": len(FILLS),
            "items": {
                "type": "object",
                "required": ["tag", "label"],
                "properties": {"tag": {"type": "string"}, "label": {"type": "string"}},
            },
        },
    },
}

PROPS_SCHEMA = {"type": "object", "additionalProperties": False, "properties": {}}


class Block(NamedTuple):
    """一个要画的块：种类 title / group / group_title / sub / sub_title / item / swatch / legend；数据路径（没有文字的是 None）；box；文字；底色 token。"""
    kind: str
    path: tuple | None
    box: tuple
    text: str | None = None
    fill: str | None = None


class Slot(NamedTuple):
    """组里排好的一行：普通条目（idxs 是这一行各条目的下标，need 是行高下限），或一个分组框（idxs 只有它自己，inner 是它里面的行）。"""
    idxs: tuple
    need: float = 0
    inner: tuple | None = None


def _columns(items, declared) -> int:
    """没写 columns 时：4 个普通条目排 2 × 2，其余每行最多 3 个（少于 3 个则占满一行）。"""
    if declared:
        return declared
    plain = sum(1 for item in items if not item.get("items") and not item.get("wide"))
    return 2 if plain == 4 else min(3, max(plain, 1))


def _rows(items, columns) -> list[tuple]:
    """把条目排成行：普通条目依次填满一行（最后一行不满就拉宽占满）；wide 条目和带 items 的分组框各占一整行，并截断当前行。"""
    rows, pending = [], []
    for i, item in enumerate(items):
        if item.get("items") or item.get("wide"):
            if pending:
                rows.append(tuple(pending))
                pending = []
            rows.append((i,))
        else:
            pending.append(i)
            if len(pending) == columns:
                rows.append(tuple(pending))
                pending = []
    if pending:
        rows.append(tuple(pending))
    return rows


def _slots(items, columns, w) -> tuple[Slot, ...]:
    """items 在 w 宽的区域里排成的行；行高下限由这一行里文字最多的条目决定（按估算行数）。"""
    slots = []
    for idxs in _rows(items, _columns(items, columns)):
        item = items[idxs[0]]
        if item.get("items"):
            slots.append(Slot(idxs, inner=_slots(item["items"], item.get("columns"), w - 2 * PAD)))
            continue
        iw = (w - ITEM_GAP * (len(idxs) - 1)) / len(idxs)
        need = max(MIN_ROW_H, *(_lines(items[i]["name"], iw - 2 * INSET_X, EM) * LINE_H + 2 * INSET_Y for i in idxs))
        slots.append(Slot(idxs, need))
    return tuple(slots)


def _tally(slots) -> tuple[float, float, int]:
    """(固定高度, 行高下限之和, 行数)：固定高度 = 行间距 + 分组框的标题和内边距。"""
    fixed, need, count = ROW_GAP * (len(slots) - 1), 0.0, 0
    for slot in slots:
        if slot.inner is None:
            need, count = need + slot.need, count + 1
        else:
            f, n, c = _tally(slot.inner)
            fixed, need, count = fixed + SUB_TOP + SUB_BOTTOM + f, need + n, count + c
    return fixed, need, count


def _height(slots, row_h) -> float:
    return ROW_GAP * (len(slots) - 1) + sum(
        row_h(s.need) if s.inner is None else SUB_TOP + SUB_BOTTOM + _height(s.inner, row_h) for s in slots)


def _place(out, slots, items, path, x, y, w, row_h, fills) -> float:
    """从 (x, y) 起、在 w 宽的区域里自上而下画出各行（分组框先画面板和标题，再画里面的行），返回最后一行的下沿。"""
    for n, slot in enumerate(slots):
        if n:
            y += ROW_GAP
        if slot.inner is not None:
            i = slot.idxs[0]
            h = SUB_TOP + SUB_BOTTOM + _height(slot.inner, row_h)
            out.append(Block("sub", None, (x, y, w, h)))
            out.append(Block("sub_title", (*path, i, "name"), (x + PAD, y + TITLE_TOP, w - 2 * PAD, SUB_TITLE_H), items[i]["name"]))
            _place(out, slot.inner, items[i]["items"], (*path, i, "items"), x + PAD, y + SUB_TOP, w - 2 * PAD, row_h, fills)
            y += h
            continue
        h = row_h(slot.need)
        iw = (w - ITEM_GAP * (len(slot.idxs) - 1)) / len(slot.idxs)
        for k, i in enumerate(slot.idxs):
            out.append(Block("item", (*path, i, "name"), (x + k * (iw + ITEM_GAP), y, iw, h), items[i]["name"],
                             fills.get(items[i].get("tag"), FILLS[0])))
        y += h
    return y


def _text_w(text: str, em: float) -> float:
    return sum(em if ord(c) > 0x2E7F else em * ASCII_EM for c in text)


def _plan(data, box) -> list[Block]:
    """把 box 划成要画的块，先画的在前（面板在文字和条目之下）。check 和 render 共用这一份，保证检查的就是画出来的。

    纵向：总标题（可选）→ 各分组 →（底部）图例。每个分组 = 组名 + 若干行；每行高度 = 它里面文字最多的条目所需的高度，
    有富余高度时平均分给所有行（单行最高 MAX_ROW_H），多出来的留在图例之上。内容多到放不下时照常往下排，由 check 报错。
    横向：分组面板占满 box 的宽度；一行的条目平分面板内的宽度。"""
    x, y, w, h = box
    legend = data.get("legend", [])
    fills = {entry["tag"]: FILLS[i] for i, entry in enumerate(legend)}
    out = []
    if data.get("title"):
        out.append(Block("title", ("title",), (x, y, w, TITLE_H), data["title"]))
        y += TITLE_H + TITLE_GAP
    bottom = box[1] + h - (LEGEND_H + LEGEND_GAP if legend else 0)

    groups = [(g, _slots(g["items"], g.get("columns"), w - 2 * PAD)) for g in data["groups"]]
    tallies = [_tally(slots) for _, slots in groups]
    fixed = sum(f + GROUP_TOP + PAD for f, _, _ in tallies) + GROUP_GAP * (len(groups) - 1)
    spare = max(bottom - y - fixed - sum(n for _, n, _ in tallies), 0) / sum(c for _, _, c in tallies)

    def row_h(need):
        return max(need, min(need + spare, MAX_ROW_H))

    for i, (group, slots) in enumerate(groups):
        gh = GROUP_TOP + _height(slots, row_h) + PAD
        out.append(Block("group", None, (x, y, w, gh)))
        out.append(Block("group_title", ("groups", i, "name"), (x + PAD, y + TITLE_TOP, w - 2 * PAD, TITLE_H), group["name"]))
        _place(out, slots, group["items"], ("groups", i, "items"), x + PAD, y + GROUP_TOP, w - 2 * PAD, row_h, fills)
        y += gh + GROUP_GAP

    lx = x
    for i, entry in enumerate(legend):
        tw = _text_w(entry["label"], EM_DETAIL) + 8
        out.append(Block("swatch", None, (lx, box[1] + h - (LEGEND_H + SWATCH) / 2, SWATCH, SWATCH), None, FILLS[i]))
        out.append(Block("legend", ("legend", i, "label"), (lx + SWATCH + SWATCH_GAP, box[1] + h - LEGEND_H, tw, LEGEND_H), entry["label"]))
        lx += SWATCH + SWATCH_GAP + tw + ENTRY_GAP
    return out


def _tag_problems(data) -> list[tuple[tuple, str]]:
    """tag 要在 legend 里定义，legend 的 tag 不能重复；有 items 的条目是分组框，不能再写 tag / wide。"""
    legend = data.get("legend", [])
    tags = [entry["tag"] for entry in legend]
    problems = [(("legend", i, "tag"), f"tag「{e['tag']}」重复，每种图例的 tag 要不同") for i, e in enumerate(legend) if e["tag"] in tags[:i]]

    def walk(items, path):
        for i, item in enumerate(items):
            if item.get("items"):
                problems.extend(((*path, i, key), f"有 items 的条目是分组框，不能再写 {key}（tag 和 wide 只用在普通条目上）")
                                for key in ("tag", "wide") if item.get(key))
                walk(item["items"], (*path, i, "items"))
            elif item.get("tag") and item["tag"] not in tags:
                hint = f"，可选：{'、'.join(tags)}" if tags else "，请先在 legend 里定义"
                problems.append(((*path, i, "tag"), f"tag「{item['tag']}」不在 legend 里{hint}"))

    for g, group in enumerate(data["groups"]):
        walk(group["items"], ("groups", g, "items"))
    return problems


def check(data, box) -> list[tuple[tuple, str]]:
    """tag 要在 legend 里定义；组名、分组框标题、总标题和图例只能一行；条目名要放得进自己的框（按字数估算行数），
    英文单词不能比框宽（否则会被拦腰折断）；所有分组加起来不能超出 box 里图例之上的高度；图例要放得进一行。"""
    problems = _tag_problems(data)
    blocks = _plan(data, box)
    legend = data.get("legend", [])
    limit = box[1] + box[3] - (LEGEND_H + LEGEND_GAP if legend else 0)
    for i, group in enumerate(b for b in blocks if b.kind == "group"):
        if group.box[1] + group.box[3] > limit + 0.5:
            problems.append((("groups", i), f"第 {i + 1} 组「{data['groups'][i]['name']}」放不下：各组自上而下排，到它的下沿估算要 "
                                            f"{group.box[1] + group.box[3] - box[1]:.0f} px 高，只放得下 {limit - box[1]:.0f} px，"
                                            f"请减少分组 / 条目的行数，或缩短条目名称让每个条目一行写完"))
            break
    for b in blocks:
        if b.text is None:
            continue
        em = EM_TITLE if b.kind in ("title", "group_title") else EM_DETAIL if b.kind == "legend" else EM
        avail = b.box[2] - 2 * (INSET_X if b.kind == "item" else TITLE_INSET)
        word = max(re.findall(r"[\x21-\x7e]+", b.text), key=len, default="")
        if len(word) * em * ASCII_EM > avail:
            problems.append((b.path, f"英文单词「{word}」比 {b.box[2]:.0f} px 宽的框还宽，会被拦腰折断，请换短一点的写法，或减少每行条目数"))
        elif b.kind not in ("item", "legend") and (avail < em or _lines(b.text, avail, em) > 1):
            problems.append((b.path, f"「{b.text}」在 {b.box[2]:.0f} px 宽的框里估算要 {_lines(b.text, avail, em)} 行，只放得下 1 行，请缩短文字"))
    if legend and (end := max(b.box[0] + b.box[2] for b in blocks if b.kind == "legend")) > box[0] + box[2] + 0.5:
        problems.append((("legend",), f"图例估算要 {end - box[0]:.0f} px 宽，只放得下 {box[2]:.0f} px，请缩短图例文字"))
    return problems


def render(slide, style, box, data, props):
    for kind, _, b, text, fill in _plan(data, box):
        if kind == "group":
            add_shape(slide, style, b, "surface")
        elif kind == "sub":
            add_shape(slide, style, b, "bg")
        elif kind == "item":
            add_shape(slide, style, b, fill, line="line", line_width=0.75, text=text, text_style="body_strong",
                      align="center", valign="middle", inset=(_inset_x("module", text, b[2]), INSET_Y))
        elif kind == "swatch":
            add_shape(slide, style, b, fill, line="line", line_width=0.75)
        elif kind == "legend":
            add_text(slide, style, b, text, "detail", valign="middle")
        else:  # 标题：总标题和组名 14 号加粗，分组框标题 12 号加粗
            text_style = "body_strong" if kind == "sub_title" else "emphasis"
            add_text(slide, style, b, text, text_style, color=None if kind == "title" else "primary", align="center", valign="middle")
