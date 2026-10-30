"""自由架构画布：用原生形状、文本和连接线表达分区架构，坐标按数据声明的参考画布缩放。"""

from pptx.enum.shapes import MSO_CONNECTOR
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Pt

from ..draw import add_shape, add_text, rgb
from ..geometry import px_to_emu

FILLS = ["bg", "surface", "surface_light", "primary", "highlight", "highlight_blue", "highlight_strong"]
LINES = ["line", "muted", "accent", "primary", "highlight_strong", "bg", "surface", "surface_light", "highlight", "highlight_blue"]
COLORS = ["accent", "highlight_strong", "primary_text", "text", "on_primary"]
STYLES = ["caption", "detail", "body", "body_strong", "emphasis"]
BOX = {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number", "minimum": 0}}
POINT = {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "number", "minimum": 0}}
SHAPE = {
    "type": "object",
    "required": ["box", "fill"],
    "additionalProperties": False,
    "properties": {
        "box": BOX,
        "fill": {"type": "string", "enum": FILLS},
        "line": {"type": "string", "enum": LINES},
        "line_width": {"type": "number", "exclusiveMinimum": 0, "maximum": 6},
        "dash": {"type": "boolean"},
        "kind": {"type": "string", "enum": ["rect", "rounded", "oval", "pentagon"]},
        "radius": {"type": "number", "exclusiveMinimum": 0},
        "text": {"type": "string"},
        "text_style": {"type": "string", "enum": STYLES},
        "color": {"type": "string", "enum": COLORS},
        "bold": {"type": "boolean"},
        "align": {"type": "string", "enum": ["left", "center", "right"]},
        "valign": {"type": "string", "enum": ["top", "middle", "bottom"]},
    },
}
TEXT = {
    "type": "object",
    "required": ["box", "text", "style"],
    "additionalProperties": False,
    "properties": {
        "box": BOX,
        "text": {"type": "string"},
        "style": {"type": "string", "enum": STYLES},
        "color": {"type": "string", "enum": COLORS},
        "bold": {"type": "boolean"},
        "align": {"type": "string", "enum": ["left", "center", "right"]},
        "valign": {"type": "string", "enum": ["top", "middle", "bottom"]},
    },
}
SCHEMA = {
    "type": "object",
    "required": ["canvas"],
    "additionalProperties": False,
    "properties": {
        "canvas": {"type": "array", "minItems": 2, "maxItems": 2,
                   "items": {"type": "number", "exclusiveMinimum": 0}},
        "panels": {"type": "array", "items": SHAPE},
        "shapes": {"type": "array", "items": SHAPE},
        "texts": {"type": "array", "items": TEXT},
        "arrows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["points"],
                "additionalProperties": False,
                "properties": {
                    "points": {"type": "array", "minItems": 2, "items": POINT},
                    "color": {"type": "string", "enum": ["muted", "primary", "accent"]},
                    "width": {"type": "number", "exclusiveMinimum": 0, "maximum": 6},
                    "head": {"type": "boolean"},
                },
            },
        },
    },
}
PROPS_SCHEMA = {"type": "object", "additionalProperties": False}


def check(data, box, props=None):
    problems = []
    cw, ch = data["canvas"]
    for group in ("panels", "shapes", "texts"):
        for i, item in enumerate(data.get(group, [])):
            x, y, w, h = item["box"]
            if w == 0 or h == 0:
                problems.append(((group, i, "box"), "宽和高必须大于 0"))
            if x + w > cw or y + h > ch:
                problems.append(((group, i, "box"), f"超出参考画布 {cw:g}×{ch:g}"))
    for i, arrow in enumerate(data.get("arrows", [])):
        for j, (x, y) in enumerate(arrow["points"]):
            if x > cw or y > ch:
                problems.append((("arrows", i, "points", j), f"超出参考画布 {cw:g}×{ch:g}"))
    return problems


def _connector(slide, style, begin, end, color, width, head):
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, *(Emu(px_to_emu(v)) for v in (*begin, *end)))
    conn._element.find(qn("p:style")).find(qn("a:effectRef")).set("idx", "0")
    conn.line.color.rgb = rgb(style, color)
    conn.line.width = Pt(width)
    if head:
        conn.line._get_or_add_ln().append(parse_xml(f'<a:tailEnd {nsdecls("a")} type="triangle"/>'))
    return conn


def render(slide, style, box, data, props):
    bx, by, bw, bh = box
    cw, ch = data["canvas"]
    sx, sy = bw / cw, bh / ch

    def map_box(values):
        x, y, w, h = values
        return bx + x * sx, by + y * sy, w * sx, h * sy

    def point(values):
        x, y = values
        return bx + x * sx, by + y * sy

    for item in data.get("panels", []):
        add_shape(slide, style, map_box(item["box"]), item["fill"], line=item.get("line"),
                  line_width=item.get("line_width", 0.75), kind=item.get("kind", "rounded"), radius=item.get("radius"),
                  dash=item.get("dash", False))

    for arrow in data.get("arrows", []):
        points = arrow["points"]
        for i, (begin, end) in enumerate(zip(points, points[1:])):
            _connector(slide, style, point(begin), point(end), arrow.get("color", "primary"),
                       arrow.get("width", 1.25), i == len(points) - 2 and arrow.get("head", True))

    for item in data.get("shapes", []):
        opts = {}
        if "text" in item:
            opts = {"text": item["text"], "text_style": item.get("text_style", "detail"),
                    "color": item.get("color"), "bold": item.get("bold"),
                    "align": item.get("align", "center"), "valign": item.get("valign", "middle"), "inset": 2}
        add_shape(slide, style, map_box(item["box"]), item["fill"], line=item.get("line"),
                  line_width=item.get("line_width", 0.75), kind=item.get("kind", "rounded"),
                  radius=item.get("radius"), dash=item.get("dash", False), **opts)

    for item in data.get("texts", []):
        add_text(slide, style, map_box(item["box"]), item["text"], item["style"], color=item.get("color"),
                 bold=item.get("bold"), align=item.get("align", "center"), valign=item.get("valign", "middle"))
