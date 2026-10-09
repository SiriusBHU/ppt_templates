"""分层架构图：左侧层名，右侧该层的模块；高亮模块 + 可选图例。"""

from ..draw import add_shape, add_text

LABEL_W, LABEL_GAP = 120, 8
ROW_GAP, PAD, MODULE_GAP = 10, 10, 10
LEGEND_H, SWATCH, SWATCH_GAP = 28, 14, 6


def _text_width(style: dict, text: str, text_style: str) -> float:
    """粗估单行文字宽度（px）：全角字符 1 em，其余 0.55 em，外加 8 px 余量。"""
    em = style["text_styles"][text_style]["size"] * 96 / 72
    return sum(em if ord(c) > 0x2E7F else em * 0.55 for c in text) + 8


def _legend(slide, style, box, text):
    x, y, w, h = box
    tw = _text_width(style, text, "caption")
    tx = x + w - tw
    add_shape(slide, style, (tx - SWATCH_GAP - SWATCH, y + (h - SWATCH) / 2, SWATCH, SWATCH), "highlight", line="highlight_strong")
    add_text(slide, style, (tx, y, tw, h), text, "caption", valign="middle")


def render(slide, style, box, layers, props):
    x, y, w, h = box
    legend = props.get("legend")
    if legend and any(m.get("highlight") for layer in layers for m in layer["modules"]):
        h -= LEGEND_H
        _legend(slide, style, (x, y + h, w, LEGEND_H), legend)

    n = len(layers)
    row_h = (h - ROW_GAP * (n - 1)) / n
    for i, layer in enumerate(layers):
        ry = y + i * (row_h + ROW_GAP)
        add_shape(slide, style, (x, ry, LABEL_W, row_h), "primary", text=layer["name"], text_style="emphasis",
                  color="on_primary", align="center", valign="middle", inset=2)

        ax, aw = x + LABEL_W + LABEL_GAP, w - LABEL_W - LABEL_GAP
        add_shape(slide, style, (ax, ry, aw, row_h), "surface")
        modules = layer["modules"]
        mw = (aw - 2 * PAD - MODULE_GAP * (len(modules) - 1)) / len(modules)
        for j, module in enumerate(modules):
            hot = module.get("highlight", False)
            add_shape(slide, style, (ax + PAD + j * (mw + MODULE_GAP), ry + PAD, mw, row_h - 2 * PAD),
                      "highlight" if hot else "bg",
                      line="highlight_strong" if hot else "line", line_width=1.5 if hot else 0.75,
                      text=module["name"], text_style="body",
                      color="highlight_strong" if hot else None, bold=True if hot else None,
                      align="center", valign="middle", inset=4)
