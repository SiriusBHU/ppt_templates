"""python-pptx 绘制原语：文字、矩形。所有 box 都是画布逻辑像素 (x, y, w, h)。"""

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls, qn
from pptx.util import Emu, Pt

from .errors import PptError
from .geometry import Box, px_to_emu

ALIGN = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}
VALIGN = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}


def rgb(style: dict, token: str) -> RGBColor:
    if token not in style["colors"]:
        raise PptError(f"未知颜色 token: {token}")
    return RGBColor.from_string(style["colors"][token].lstrip("#"))


def emu_box(box: Box) -> tuple[Emu, Emu, Emu, Emu]:
    return tuple(Emu(px_to_emu(v)) for v in box)


def _text_style(style: dict, token: str) -> dict:
    if token not in style["text_styles"]:
        raise PptError(f"未知文字样式 token: {token}")
    return style["text_styles"][token]


def add_run(p, style: dict, text: str, text_style: str, color=None, bold=None):
    """追加一个 run；显式写 a:latin / a:ea / a:cs。"""
    ts = _text_style(style, text_style)
    fonts = style["fonts"]
    run = p.add_run()
    run.text = text
    font = run.font
    font.size = Pt(ts["size"])
    font.bold = ts.get("bold", False) if bold is None else bold
    font.color.rgb = rgb(style, color or ts["color"])
    font.name = fonts["latin"]  # 只写 a:latin，a:ea / a:cs 紧随其后手动补上
    latin = run._r.rPr.find(qn("a:latin"))
    ea = parse_xml(f'<a:ea {nsdecls("a")} typeface="{fonts["cjk"]}"/>')
    cs = parse_xml(f'<a:cs {nsdecls("a")} typeface="{fonts["cjk"]}"/>')
    latin.addnext(ea)
    ea.addnext(cs)


def _setup_frame(tf, valign: str, inset: float):
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.NONE
    tf.vertical_anchor = VALIGN[valign]
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Emu(px_to_emu(inset))


def set_text(tf, style: dict, text, text_style: str, *, color=None, bold=None, align="left", valign="top", inset=0):
    """写入文字并设置文本框属性；按换行拆成段落，每段一个 run。"""
    _setup_frame(tf, valign, inset)
    for i, line in enumerate(str(text).split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = ALIGN[align]
        add_run(p, style, line, text_style, color, bold)


def add_text(slide, style: dict, box: Box, text, text_style: str, **opts):
    """纯文字框：四边内边距为 0（可用 inset 覆盖）。"""
    tb = slide.shapes.add_textbox(*emu_box(box))
    set_text(tb.text_frame, style, text, text_style, **opts)
    return tb


def add_runs(slide, style: dict, box: Box, runs, *, align="left", valign="top"):
    """单段落、多 run 的文字框（如 24 号标题 + 18 号后半句），runs = [(text, text_style), ...]。"""
    tb = slide.shapes.add_textbox(*emu_box(box))
    _setup_frame(tb.text_frame, valign, 0)
    p = tb.text_frame.paragraphs[0]
    p.alignment = ALIGN[align]
    for text, text_style in runs:
        add_run(p, style, text, text_style)
    return tb


BULLET = "•"


def add_bullets(slide, style: dict, box: Box, items, text_style: str, *, color=None):
    """要点列表：每项一段，带项目符号；项是字符串，或 {text, level}（level 从 0 起，每级多缩进一个字宽）。"""
    tb = slide.shapes.add_textbox(*emu_box(box))
    _setup_frame(tb.text_frame, "top", 0)
    em = px_to_emu(_text_style(style, text_style)["size"] * 96 / 72)
    for i, item in enumerate(items):
        text, level = (item, 0) if isinstance(item, str) else (item["text"], item.get("level", 0))
        p = tb.text_frame.paragraphs[0] if i == 0 else tb.text_frame.add_paragraph()
        p_pr = p._p.get_or_add_pPr()
        p_pr.set("marL", str(em * (level + 1)))
        p_pr.set("indent", str(-em))
        if i:  # a:pPr 子元素顺序：spcBef 必须在 buFont / buChar 之前
            p_pr.append(parse_xml(f'<a:spcBef {nsdecls("a")}><a:spcPts val="400"/></a:spcBef>'))
        p_pr.append(parse_xml(f'<a:buFont {nsdecls("a")} typeface="{style["fonts"]["latin"]}"/>'))
        p_pr.append(parse_xml(f'<a:buChar {nsdecls("a")} char="{BULLET}"/>'))
        add_run(p, style, text, text_style, color)
    return tb


def add_shape(slide, style: dict, box: Box, fill: str, *, line=None, line_width=0.75, rounded=False, text=None, **text_opts):
    """实心矩形，无阴影；line 给定才画 line_width pt 的描边。text 直接写在形状里，便于居中。"""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE, *emu_box(box))
    shape.shadow.inherit = False  # PowerPoint 认空的 a:effectLst
    shape._element.find(qn("p:style")).find(qn("a:effectRef")).set("idx", "0")  # LibreOffice 仍会按主题画阴影
    shape.fill.solid()
    shape.fill.fore_color.rgb = rgb(style, fill)
    if line:
        shape.line.color.rgb = rgb(style, line)
        shape.line.width = Pt(line_width)
    else:
        shape.line.fill.background()
    if text is not None:
        set_text(shape.text_frame, style, text, **text_opts)
    return shape
