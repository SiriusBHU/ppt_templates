"""紧凑页框（页没有 takeaway 时 body 区用 body_compact）和 lead 文字样式。"""

import re
import shutil

import pytest
import yaml

from factories import arch_template, deck_of, mini_template
from ppt_templates.errors import PptError
from ppt_templates.geometry import body_box
from ppt_templates.loader import load_style
from ppt_templates.render import render_deck

NOTE_ID = "common.summary-note"


def _px(shape):
    return tuple(v / 9525 for v in (shape.left, shape.top, shape.width, shape.height))


def _note_template(**props):
    """title + note 的页；props 加到 slots 里（如可选的 takeaway）。note 的参考 box 是 [0, 140, 600, 56]。"""
    template, _ = mini_template()
    template["slots"]["properties"].update(props)
    template["layout"] = [{"type": "text", "box": [0, 140, 600, 56], "bind": "note", "style": "body"}]
    return template


def _render(make_repo, template, data, **kw):
    repo = make_repo({template["id"]: (template, None)}, **kw)
    return list(render_deck(deck_of(template["id"], data), repo).slides[0].shapes)


def _text(shapes, text):
    return next(sh for sh in shapes if sh.has_text_frame and sh.text_frame.text == text)


# ---- 默认风格 ----

def test_default_style_compact_body_starts_16px_below_the_title_and_keeps_the_bottom_edge(root):
    frame = load_style(root, "default")["frame"]
    (tx, ty, tw, th), (x, y, w, h), (cx, cy, cw, ch) = (frame[k]["box"] for k in ("title", "body", "body_compact"))
    assert frame["body_compact"]["box"] == [32, 88, 1216, 600]
    assert (cx, cw) == (x, w) and cy == ty + th + 16 and cy + ch == y + h == 688


def test_body_box_picks_compact_only_without_a_takeaway(root):
    style = load_style(root, "default")
    assert body_box(style, {"title": "t"}) == (32, 88, 1216, 600)
    assert body_box(style, {"title": "t", "takeaway": ""}) == (32, 88, 1216, 600)
    assert body_box(style, {"title": "t", "takeaway": "结论"}) == (32, 128, 1216, 560)


def test_body_box_falls_back_to_body_when_the_style_has_no_body_compact(root):
    style = load_style(root, "default")
    del style["frame"]["body_compact"]
    assert body_box(style, {"title": "t"}) == (32, 128, 1216, 560)


# ---- 渲染 ----

def test_page_without_takeaway_uses_the_compact_body_and_scales_y(make_repo):
    shapes = _render(make_repo, _note_template(), {"title": "t", "note": "正文"}, compact_body=True)
    # 参考 box [0, 140, 600, 56] → x 不缩放（宽都是 1216），y / h 乘 600/560：32 + 0, 88 + 150, 600 × 60
    assert _px(_text(shapes, "正文")) == pytest.approx((32, 88 + 150, 600, 60))


@pytest.mark.parametrize("data", [{"title": "t", "note": "正文"}, {"title": "t", "note": "正文", "takeaway": ""}])
def test_missing_or_empty_takeaway_is_compact_and_draws_no_takeaway_box(make_repo, data):
    template = _note_template(takeaway={"type": "string", "maxLength": 40})
    shapes = _render(make_repo, template, data, compact_body=True)
    assert _px(_text(shapes, "正文")) == pytest.approx((32, 238, 600, 60))
    assert [sh.text_frame.text for sh in shapes if sh.has_text_frame] == ["t", "正文"]  # 没有空的 takeaway 文本框


def test_page_with_takeaway_keeps_the_standard_body(make_repo):
    template = _note_template(takeaway={"type": "string", "maxLength": 40})
    shapes = _render(make_repo, template, {"title": "t", "note": "正文", "takeaway": "一句话结论"}, compact_body=True)
    assert _px(_text(shapes, "正文")) == (32, 128 + 140, 600, 56)
    assert _px(_text(shapes, "一句话结论")) == (32, 76, 1216, 30)


def test_title_position_does_not_depend_on_the_body(make_repo):
    template = _note_template(takeaway={"type": "string", "maxLength": 40})
    with_takeaway = _render(make_repo, template, {"title": "标题", "note": "正文", "takeaway": "结论"}, compact_body=True)
    assert _px(_text(with_takeaway, "标题")) == (32, 32, 1216, 40)


def test_style_without_body_compact_renders_like_the_standard_body(make_repo):
    shapes = _render(make_repo, _note_template(), {"title": "t", "note": "正文"})  # make_repo 默认去掉 body_compact
    assert _px(_text(shapes, "正文")) == (32, 128 + 140, 600, 56)


def test_font_sizes_do_not_scale_with_the_body(make_repo):
    shapes = _render(make_repo, _note_template(), {"title": "t", "note": "正文"}, compact_body=True)
    assert _text(shapes, "正文").text_frame.paragraphs[0].runs[0].font.size.pt == 12


def _narrow_compact_body(repo):
    path = repo / "styles" / "default" / "style.yaml"
    style = yaml.safe_load(path.read_text(encoding="utf-8"))
    style["frame"]["body_compact"]["box"] = [32, 88, 400, 600]  # 只有紧凑 body 比参考尺寸窄得多
    path.write_text(yaml.safe_dump(style, allow_unicode=True), encoding="utf-8")


def test_component_checks_see_the_scaled_compact_box(make_repo):
    template, example = arch_template()
    repo = make_repo({template["id"]: (template, example)}, compact_body=True)
    _narrow_compact_body(repo)
    with pytest.raises(PptError, match="组件 partitioned-arch  /partitions/"):
        render_deck(deck_of(template["id"], example), repo)


def test_component_checks_use_the_standard_box_when_there_is_a_takeaway(make_repo):
    template, example = arch_template()
    template["slots"]["properties"]["takeaway"] = {"type": "string", "maxLength": 40}
    repo = make_repo({template["id"]: (template, example)}, compact_body=True)
    _narrow_compact_body(repo)
    assert render_deck(deck_of(template["id"], {**example, "takeaway": "有结论就用标准 body"}), repo)


# ---- 风格 schema ----

def _patched_style(root, tmp_path, patch):
    shutil.copytree(root / "schema", tmp_path / "schema")
    shutil.copytree(root / "styles", tmp_path / "styles")
    path = tmp_path / "styles" / "default" / "style.yaml"
    style = yaml.safe_load(path.read_text(encoding="utf-8"))
    patch(style)
    path.write_text(yaml.safe_dump(style, allow_unicode=True), encoding="utf-8")
    return tmp_path


def test_body_compact_is_optional(root, tmp_path):
    load_style(_patched_style(root, tmp_path, lambda s: s["frame"].pop("body_compact")), "default")


@pytest.mark.parametrize("patch, message", [
    (lambda s: s["frame"].update(body_compact={}), "/frame/body_compact  缺少必填字段 box"),
    (lambda s: s["frame"].update(body_compact={"box": [32, 88, 1216]}), "/frame/body_compact/box  共 3 项，低于下限 4"),
    (lambda s: s["frame"]["body_compact"].update(extra=1), "/frame/body_compact  不允许的字段 extra"),
])
def test_body_compact_must_be_a_box(root, tmp_path, patch, message):
    with pytest.raises(PptError, match=re.escape(message)):
        load_style(_patched_style(root, tmp_path, patch), "default")


# ---- lead ----

def test_lead_is_14pt_regular_in_the_text_color(root):
    style = load_style(root, "default")
    assert style["text_styles"]["lead"] == {"size": 14, "color": "text"}
    assert style["text_styles"]["emphasis"]["bold"] is True  # 14 号加粗仍是 emphasis


@pytest.mark.parametrize("patch, message", [
    (lambda s: s["text_styles"]["lead"].update(size=12), "/text_styles/lead/size  必须是 14，实际是 12"),
    (lambda s: s["text_styles"].pop("lead"), "/text_styles  缺少必填字段 lead"),
])
def test_lead_is_required_and_fixed_at_14pt(root, tmp_path, patch, message):
    with pytest.raises(PptError, match=re.escape(message)):
        load_style(_patched_style(root, tmp_path, patch), "default")


def test_lead_text_renders_as_14pt_non_bold_black(make_repo):
    template = _note_template()
    template["layout"][0]["style"] = "lead"
    run = _text(_render(make_repo, template, {"title": "t", "note": "正文"}), "正文").text_frame.paragraphs[0].runs[0]
    assert (run.font.size.pt, bool(run.font.bold), str(run.font.color.rgb)) == (14, False, "000000")
