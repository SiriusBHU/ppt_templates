"""框图 / 流程图：节点按内容给出的 [行, 列] 放进网格，边是节点之间带箭头的直线连接（v1 不做自动布局）。"""

from pptx.enum.shapes import MSO_CONNECTOR
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls
from pptx.util import Pt

from ..draw import add_shape, add_text, rgb
from ..errors import PptError
from ..geometry import EMU_PER_PX

GAP_X, GAP_Y = 48, 32        # 节点之间的水平 / 垂直间距（px），留给连线和标签
LABEL_W, LABEL_H = 120, 16   # 连线标签的文字框
TOP, LEFT, BOTTOM, RIGHT = 0, 1, 2, 3  # 矩形的连接点编号

SCHEMA = {
    "type": "object",
    "required": ["nodes"],
    "properties": {
        "nodes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "name", "pos"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "pos": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer", "minimum": 0}},
                    "highlight": {"type": "boolean"},
                },
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["from", "to"],
                "properties": {"from": {"type": "string"}, "to": {"type": "string"}, "label": {"type": "string"}},
            },
        },
    },
}


def _sites(src, dst) -> tuple[int, int]:
    """按两节点的相对位置选连接点：水平方向占优就左右相连，否则上下相连。"""
    (r1, c1), (r2, c2) = src, dst
    if abs(c2 - c1) >= abs(r2 - r1):
        return (RIGHT, LEFT) if c2 > c1 else (LEFT, RIGHT)
    return (BOTTOM, TOP) if r2 > r1 else (TOP, BOTTOM)


def _check(nodes, edges) -> dict:
    by_id, cells = {}, set()
    for n in nodes:
        pos = tuple(n["pos"])
        if n["id"] in by_id:
            raise PptError(f"框图节点 id 重复: {n['id']}")
        if pos in cells:
            raise PptError(f"框图节点位置重复: {list(pos)}")
        by_id[n["id"]] = n
        cells.add(pos)
    for e in edges:
        for end in ("from", "to"):
            if e[end] not in by_id:
                raise PptError(f"框图连线引用了不存在的节点: {e[end]}")
    return by_id


def render(slide, style, box, data, props):
    nodes, edges = data["nodes"], data.get("edges", [])
    by_id = _check(nodes, edges)
    rows = max(n["pos"][0] for n in nodes) + 1
    cols = max(n["pos"][1] for n in nodes) + 1
    x, y, w, h = box
    nw = (w - GAP_X * (cols - 1)) / cols
    nh = (h - GAP_Y * (rows - 1)) / rows

    shapes = {}
    for n in nodes:
        r, c = n["pos"]
        hot = n.get("highlight", False)
        shapes[n["id"]] = add_shape(
            slide, style, (x + c * (nw + GAP_X), y + r * (nh + GAP_Y), nw, nh),
            "highlight" if hot else "bg",
            line="highlight_strong" if hot else "line", line_width=1.5 if hot else 0.75,
            text=n["name"], text_style="body",
            color="highlight_strong" if hot else None, bold=True if hot else None,
            align="center", valign="middle", inset=4)

    for e in edges:
        begin, end = _sites(by_id[e["from"]]["pos"], by_id[e["to"]]["pos"])
        conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, 0, 0, 0)
        conn.begin_connect(shapes[e["from"]], begin)
        conn.end_connect(shapes[e["to"]], end)
        conn.line.color.rgb = rgb(style, "muted")
        conn.line.width = Pt(1)
        conn.line._get_or_add_ln().append(parse_xml(f'<a:tailEnd {nsdecls("a")} type="triangle"/>'))
        if e.get("label"):
            mx = (conn.begin_x + conn.end_x) / 2 / EMU_PER_PX
            my = (conn.begin_y + conn.end_y) / 2 / EMU_PER_PX
            if begin in (LEFT, RIGHT):  # 水平线：标签在线的上方
                label_box = (mx - LABEL_W / 2, my - LABEL_H - 2, LABEL_W, LABEL_H)
            else:                       # 垂直线：标签在线的右侧
                label_box = (mx + 6, my - LABEL_H / 2, LABEL_W, LABEL_H)
            add_text(slide, style, label_box, e["label"], "caption",
                     align="center" if begin in (LEFT, RIGHT) else "left")
