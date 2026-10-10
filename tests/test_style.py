import re
import shutil

import pytest
import yaml

from ppt_templates.errors import PptError
from ppt_templates.loader import load_style


def test_default_style_is_valid(root):
    assert load_style(root, "default")["fonts"] == {"cjk": "微软雅黑", "latin": "微软雅黑"}


@pytest.mark.parametrize("patch, message", [
    (lambda s: s["text_styles"]["body"].update(size=13), "/text_styles/body/size  必须是 12，实际是 13"),
    (lambda s: s["text_styles"]["title"].update(size=18), "/text_styles/title/size  必须是 24，实际是 18"),
    (lambda s: s["text_styles"].update(h3={"size": 14, "color": "text"}), "/text_styles  不允许的字段 h3"),
    (lambda s: s["fonts"].update(latin="Arial"), "/fonts/latin  必须是 微软雅黑，实际是 Arial"),
    (lambda s: s["colors"].update(accent="blue"), "/colors/accent  blue 不符合格式"),
    (lambda s: s["frame"].pop("body"), "/frame  缺少必填字段 body"),
    (lambda s: s["shadow"].update(alpha=0), "/shadow/alpha  取值 0，必须大于 0"),
    (lambda s: s["shadow"].update(alpha=1.5), "/shadow/alpha  取值 1.5，超过上限 1"),
    (lambda s: s["shadow"].update(blur=-1), "/shadow/blur  取值 -1，低于下限 0"),
    (lambda s: s["shadow"].pop("angle"), "/shadow  缺少必填字段 angle"),
    (lambda s: s["shadow"].update(spread=2), "/shadow  不允许的字段 spread"),
])
def test_style_constraints_are_enforced(root, tmp_path, patch, message):
    shutil.copytree(root / "schema", tmp_path / "schema")
    shutil.copytree(root / "styles", tmp_path / "styles")
    path = tmp_path / "styles" / "default" / "style.yaml"
    style = yaml.safe_load(path.read_text(encoding="utf-8"))
    patch(style)
    path.write_text(yaml.safe_dump(style, allow_unicode=True), encoding="utf-8")
    with pytest.raises(PptError, match=re.escape(message)):
        load_style(tmp_path, "default")


@pytest.mark.parametrize("patch", [
    lambda s: s.pop("shadow"),
    lambda s: s["frame"].pop("decorations", None),
    lambda s: s["frame"].update(decorations=[]),
])
def test_shadow_and_decorations_are_optional(root, tmp_path, patch):
    shutil.copytree(root / "schema", tmp_path / "schema")
    shutil.copytree(root / "styles", tmp_path / "styles")
    path = tmp_path / "styles" / "default" / "style.yaml"
    style = yaml.safe_load(path.read_text(encoding="utf-8"))
    patch(style)
    path.write_text(yaml.safe_dump(style, allow_unicode=True), encoding="utf-8")
    load_style(tmp_path, "default")
