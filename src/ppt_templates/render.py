"""deck → Presentation：页框 + 布局元素（shape / text / grid / component）。"""

from pathlib import Path

from pptx import Presentation
from pptx.util import Emu

from .components import COMPONENTS
from .draw import add_runs, add_shape, add_text
from .errors import PptError
from .geometry import CANVAS_H, CANVAS_W, REF_H, REF_W, Transform, grid_cells, px_to_emu, resolve_box
from .loader import load_style
from .slots import prepare_pages

BLANK_LAYOUT = 6
FRAME_DEFAULT_STYLE = {"title": "title", "title_suffix": "title_suffix", "takeaway": "subtitle"}
CANVAS_AREA = (0, 0, CANVAS_W, CANVAS_H)


def render_deck(deck: dict, root: Path) -> Presentation:
    pages = prepare_pages(deck, root)
    style = load_style(root, deck.get("style", "default"))
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(px_to_emu(CANVAS_W)), Emu(px_to_emu(CANVAS_H))
    for template, data in pages:
        slide = prs.slides.add_slide(prs.slide_layouts[BLANK_LAYOUT])
        if template.get("frame", "standard") == "standard":
            _render_frame(slide, style, data)
            bx, by, bw, bh = style["frame"]["body"]["box"]
            _render_elements(slide, style, template["layout"], (0, 0, REF_W, REF_H), data, Transform(bx, by, bw / REF_W, bh / REF_H))
        else:
            _render_elements(slide, style, template["layout"], CANVAS_AREA, data, Transform())
    return prs


def _render_frame(slide, style, data):
    frame = style["frame"]
    _render_elements(slide, style, frame.get("decorations", []), CANVAS_AREA, {}, Transform())
    regions = {name: data[name] for name in ("title", "takeaway") if name in data}
    for name, text in regions.items():
        region = frame[name]
        box = resolve_box(region["box"], CANVAS_W, CANVAS_H)
        text_style = region.get("style", FRAME_DEFAULT_STYLE[name])
        align, valign = region.get("align", "left"), region.get("valign", "top")
        if name == "title" and data.get("title_suffix"):
            # 标题主体与后半句同一行、共用基线；全角空格隔开
            suffix_style = region.get("suffix_style", FRAME_DEFAULT_STYLE["title_suffix"])
            add_runs(slide, style, box, [(text, text_style), ("　" + data["title_suffix"], suffix_style)],
                     align=align, valign=valign)
        else:
            add_text(slide, style, box, text, text_style, align=align, valign=valign)


def _lookup(scope, path: str):
    """点号路径相对 scope 解析；"." 是 scope 本身；缺失（可选槽位未填）返回 None。"""
    if path == ".":
        return scope
    for key in path.split("."):
        if not isinstance(scope, dict) or key not in scope:
            return None
        scope = scope[key]
    return scope


def _render_elements(slide, style, elements, area, scope, tf):
    """area = 父区域 (x, y, w, h)，在参考坐标系中；tf 把参考坐标映射到画布。"""
    ax, ay, aw, ah = area
    for el in elements:
        x, y, w, h = resolve_box(el["box"], aw, ah)
        ref_box = (ax + x, ay + y, w, h)
        kind = el["type"]
        if kind == "shape":
            add_shape(slide, style, tf(ref_box), el["fill"], line=el.get("line"), rounded=el.get("shape") == "rounded")
        elif kind == "text":
            text = el["value"] if "value" in el else _lookup(scope, el["bind"])
            if text is not None:
                add_text(slide, style, tf(ref_box), text, el["style"], color=el.get("color"),
                         align=el.get("align", "left"), valign=el.get("valign", "top"))
        elif kind == "grid":
            items = _lookup(scope, el["bind"]) or []
            for item, cell in zip(items, grid_cells(ref_box, el["columns"], el.get("gap", 0), len(items))):
                _render_elements(slide, style, el["item"], cell, item, tf)
        elif kind == "component":
            if el["component"] not in COMPONENTS:
                raise PptError(f"未知组件: {el['component']}")
            data = _lookup(scope, el["bind"])
            if data is not None:
                COMPONENTS[el["component"]](slide, style, tf(ref_box), data, el.get("props", {}))
        else:
            raise PptError(f"不支持的布局元素类型: {kind}")
