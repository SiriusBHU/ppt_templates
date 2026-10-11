"""组件 props 里能写的颜色 / 文字样式 token：与 schema/style.schema.json 的必填项一致，props 校验时用作 enum。"""

import json
from pathlib import Path

_STYLE_SCHEMA = json.loads((Path(__file__).resolve().parents[3] / "schema" / "style.schema.json").read_text(encoding="utf-8"))
COLOR_TOKENS = tuple(_STYLE_SCHEMA["properties"]["colors"]["required"])
TEXT_STYLES = tuple(_STYLE_SCHEMA["properties"]["text_styles"]["required"])
COLOR = {"enum": list(COLOR_TOKENS)}
TEXT_STYLE = {"enum": list(TEXT_STYLES)}
