import shutil

import pytest
import yaml
from lxml import etree
from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.util import Emu, Pt

from ppt_templates.cli import main
from ppt_templates.errors import PptError
from ppt_templates.importer import import_skeleton


def px(v):
    """1280 宽画布上的 px → EMU（标准 16:9 页宽 12192000 EMU，每 px 9525）。"""
    return Emu(round(v * 9525))


def _run(shape_or_cell, text, size=12, bold=False, color="000000", new_paragraph=False):
    tf = shape_or_cell.text_frame
    para = tf.add_paragraph() if new_paragraph else tf.paragraphs[0]
    run = para.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)
    return run


def _box(slide, kind, x, y, w, h, fill=None):
    shape = slide.shapes.add_shape(kind, px(x), px(y), px(w), px(h))
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    else:
        shape.fill.background()
    shape.line.fill.background()
    return shape


def _title(slide, text="问题现状", x=32, y=32):
    box = slide.shapes.add_textbox(px(x), px(y), px(800), px(40))
    _run(box, text, size=24, bold=True, color="C00000")
    return box


def build(path, width=12192000, height=6858000):
    """3 页：1 = 标准页（标题 + 卡片 + 组 + 表格 + 图片占位 + 箭头线）；2 = 无标题的整页底色；3 = 有标题但顶部有色条。"""
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(width), Emu(height)
    blank = prs.slide_layouts[6]

    s1 = prs.slides.add_slide(blank)
    _title(s1)
    card = _box(s1, MSO_SHAPE.ROUNDED_RECTANGLE, 64, 160, 300, 100, fill="F3F5F8")
    _run(card, "名称：", size=12, bold=True)
    _run(card, "说明文字", size=12)
    _run(card, "约十一磅", size=11, new_paragraph=True, color="595959")
    _run(card, "十六磅加粗", size=16, bold=True, new_paragraph=True, color="FFFFFF")
    card._element.spPr.append(etree.fromstring(
        '<a:effectLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:outerShdw blurRad="63500" dist="19050" dir="5400000"/></a:effectLst>'))
    near = _box(s1, MSO_SHAPE.OVAL, 400, 160, 40, 40, fill="E8ECF4")
    near.name = "近似色"

    group = s1.shapes.add_group_shape()
    group.shapes.add_shape(MSO_SHAPE.RECTANGLE, px(100), px(300), px(50), px(40))
    inner = group.shapes.add_textbox(px(160), px(300), px(100), px(40))
    _run(inner, "组内文字", size=10)
    xfrm = group._element.grpSpPr.find(qn("a:xfrm"))
    ext = xfrm.find(qn("a:ext"))
    ext.set("cx", str(int(ext.get("cx")) * 2))  # 组被放大 2 倍：子形状坐标要按 off + (子 - chOff) * 2 还原
    ext.set("cy", str(int(ext.get("cy")) * 2))

    table = s1.shapes.add_table(2, 2, px(64), px(400), px(600), px(100)).table
    _run(table.cell(0, 0), "指标", size=10, bold=True)
    _run(table.cell(0, 1), "数值", size=10, bold=True)
    _run(table.cell(1, 0), "带宽", size=9)
    _run(table.cell(1, 1), "7 GB/s", size=9)

    holder = _box(s1, MSO_SHAPE.RECTANGLE, 700, 160, 300, 200, fill="D9D9D9")
    _run(holder, "图片", size=12)

    line = s1.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, px(64), px(380), px(364), px(380))
    line.line.color.rgb = RGBColor.from_string("6B7280")
    line.line.width = Pt(1.5)
    line.line._get_or_add_ln().append(etree.fromstring(
        '<a:tailEnd xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" type="triangle"/>'))

    themed = _box(s1, MSO_SHAPE.RECTANGLE, 1000, 400, 40, 40)
    themed.fill.solid()
    themed.fill.fore_color.theme_color = MSO_THEME_COLOR.BACKGROUND_1  # 主题色 bg1 → 白

    s2 = prs.slides.add_slide(blank)
    _box(s2, MSO_SHAPE.RECTANGLE, 0, 0, 1280, 720, fill="283593")
    s3 = prs.slides.add_slide(blank)
    _title(s3, "顶部有色条")
    _box(s3, MSO_SHAPE.RECTANGLE, 0, 0, 1280, 16, fill="C00000")
    prs.save(path)
    return path


@pytest.fixture
def no_soffice(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)


def run_import(root, tmp_path, slides=None, **build_args):
    pptx = build(tmp_path / "skeleton.pptx", **build_args)
    dirs, warnings = import_skeleton(root, pptx, tmp_path / "out", slides)
    docs = [yaml.safe_load((d / "shapes.yaml").read_text(encoding="utf-8")) for d in dirs]
    return docs, warnings


def by_name(shapes, name):
    return next(s for s in shapes if s["name"] == name)


def of_kind(shapes, kind):
    return [s for s in shapes if s["kind"] == kind]


def test_writes_one_directory_per_selected_slide(root, tmp_path, no_soffice):
    pptx = build(tmp_path / "skeleton.pptx")
    dirs, _ = import_skeleton(root, pptx, tmp_path / "out", [3, 1, 3])
    assert [d.relative_to(tmp_path / "out").as_posix() for d in dirs] == ["slide-3", "slide-1"]
    assert all((d / "shapes.yaml").is_file() for d in dirs)
    assert not (tmp_path / "out" / "slide-2").exists()


def test_slide_out_of_range(root, tmp_path, no_soffice):
    with pytest.raises(PptError, match="页码 4 超出范围（共 3 页）"):
        import_skeleton(root, build(tmp_path / "skeleton.pptx"), tmp_path / "out", [1, 4])


def test_missing_file(root, tmp_path):
    with pytest.raises(PptError, match="文件不存在"):
        import_skeleton(root, tmp_path / "nope.pptx", tmp_path / "out")


def test_boxes_are_logical_px_and_relative_to_the_standard_body(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    assert doc["canvas"] == [1280, 720] and doc["body_origin"] == [32, 128]
    title = of_kind(doc["shapes"], "textbox")[0]
    assert title["box"] == [32, 32, 800, 40] and title["body_box"] == [0, -96, 800, 40]
    card = of_kind(doc["shapes"], "rounded")[0]
    assert card["box"] == [64, 160, 300, 100] and card["body_box"] == [32, 32, 300, 100]


def test_px_scale_follows_the_slide_width(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1], width=24384000, height=13716000)  # 页宽翻倍：同样的 EMU 只占一半 px
    assert of_kind(doc["shapes"], "textbox")[0]["box"] == [16, 16, 400, 20]


def test_non_16_9_slide_warns(root, tmp_path, no_soffice):
    _, warnings = run_import(root, tmp_path, [1], height=9144000)
    assert any("不是 16:9" in w for w in warnings)


def test_kinds_fills_and_shadow(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    card = of_kind(doc["shapes"], "rounded")[0]
    assert card["fill"] == {"hex": "#F3F5F8", "token": "surface"} and card["shadow"] is True and "line" not in card
    oval = by_name(doc["shapes"], "近似色")
    assert oval["kind"] == "oval" and oval["shadow"] is False
    assert oval["fill"] == {"hex": "#E8ECF4", "token": "surface", "approx": True}
    themed = [s for s in of_kind(doc["shapes"], "rect") if s["box"][:2] == [1000, 400]][0]
    assert themed["fill"] == {"hex": "#FFFFFF", "token": "bg"}  # 主题色 bg1 解析为白，再映射到 bg


def test_text_size_style_and_color_tokens(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    title = of_kind(doc["shapes"], "textbox")[0]["text"][0]
    assert title == {"text": "问题现状", "size": 24, "style": "title", "bold": True,
                     "color": {"hex": "#C00000", "token": "accent"}, "align": "left"}
    card = of_kind(doc["shapes"], "rounded")[0]
    first, small, big = card["text"]
    assert (first["size"], first["style"], first["bold"]) == (12, "body_strong", True)
    assert (small["size"], small["style"]) == (11, "body")  # 11pt 与 10 / 12 等距，取大的
    assert small["color"] == {"hex": "#595959", "token": "text", "approx": True}  # 文字颜色只在允许的几种里选
    assert (big["size"], big["style"], big["bold"]) == (16, "title_suffix", True)  # 18 且加粗 → title_suffix
    assert big["color"] == {"hex": "#FFFFFF", "token": "on_primary"}
    assert card["valign"] == "middle" and of_kind(doc["shapes"], "textbox")[0]["valign"] == "top"


def test_mixed_runs_in_a_paragraph_are_listed(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    para = of_kind(doc["shapes"], "rounded")[0]["text"][0]
    assert para["text"] == "名称：说明文字"
    assert [(r["text"], r["style"]) for r in para["runs"]] == [("名称：", "body_strong"), ("说明文字", "body")]
    assert "runs" not in of_kind(doc["shapes"], "textbox")[0]["text"][0]  # 单一样式的段落不列 runs


def test_group_children_are_recursed_with_the_group_transform(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    group = of_kind(doc["shapes"], "group")[0]
    assert group["box"] == [100, 300, 320, 80]
    rect, text = group["children"]
    assert rect["kind"] == "rect" and rect["box"] == [100, 300, 100, 80]
    assert text["kind"] == "textbox" and text["box"] == [220, 300, 200, 80]
    assert text["text"][0]["text"] == "组内文字" and text["text"][0]["style"] == "detail"


def test_table_is_recursed_into_cells(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    table = of_kind(doc["shapes"], "table")[0]
    assert table["box"] == [64, 400, 600, 100]
    t = table["table"]
    assert (t["rows"], t["cols"]) == (2, 2) and t["col_widths"] == [300, 300] and t["row_heights"] == [50, 50]
    assert t["cells"][0][0]["text"][0]["text"] == "指标" and t["cells"][0][0]["text"][0]["style"] == "detail"
    assert t["cells"][1][1]["text"][0]["text"] == "7 GB/s" and t["cells"][1][1]["text"][0]["style"] == "caption"


def test_picture_chart_placeholders(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    holder = of_kind(doc["shapes"], "placeholder")[0]
    assert holder["label"] == "图片" and holder["box"] == [700, 160, 300, 200] and "text" not in holder


def test_connector_is_a_line_with_endpoints_arrow_and_width(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    line = of_kind(doc["shapes"], "line")[0]
    assert line["start"] == [64, 380] and line["end"] == [364, 380] and line["arrow"] == "end"
    assert line["line"] == {"hex": "#6B7280", "token": "muted"} and line["line_width"] == 2  # 1.5pt = 2px


def test_frame_guess(root, tmp_path, no_soffice):
    docs, _ = run_import(root, tmp_path)
    standard, full_bleed, with_bar = (d["frame_guess"] for d in docs)
    assert standard["frame"] == "standard" and "标题" in standard["reason"]
    assert full_bleed["frame"] == "none" and "没有" in full_bleed["reason"]
    assert with_bar["frame"] == "none" and "1 个元素超出 body 区" in with_bar["reason"]


def build_compact(path):
    """4 页：1 = 标题 + 紧贴标题的卡片 / 图片 / 两个 14 号文本框；2 = 标题 + 副标题 + 卡片；3 = 紧贴标题但卡片超出底边；4 = 14 号文字。"""
    Image.new("RGB", (20, 10), "red").save(path.with_suffix(".png"))
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(12192000), Emu(6858000)
    blank = prs.slide_layouts[6]
    s1 = prs.slides.add_slide(blank)
    _title(s1)
    _box(s1, MSO_SHAPE.ROUNDED_RECTANGLE, 64, 96, 300, 100, fill="F3F5F8")
    s1.shapes.add_picture(str(path.with_suffix(".png")), px(400), px(96), px(200), px(140))
    s2 = prs.slides.add_slide(blank)
    _title(s2)
    sub = s2.shapes.add_textbox(px(32), px(76), px(800), px(30))
    _run(sub, "一句话结论", size=18)
    _box(s2, MSO_SHAPE.ROUNDED_RECTANGLE, 64, 140, 300, 100, fill="F3F5F8")
    s3 = prs.slides.add_slide(blank)
    _title(s3)
    _box(s3, MSO_SHAPE.RECTANGLE, 64, 96, 300, 640, fill="F3F5F8")
    s4 = prs.slides.add_slide(blank)
    _title(s4)
    plain = s4.shapes.add_textbox(px(64), px(140), px(300), px(30))
    _run(plain, "正常要点", size=14)
    strong = s4.shapes.add_textbox(px(64), px(180), px(300), px(30))
    _run(strong, "加粗重点", size=14, bold=True)
    prs.save(path)
    return path


def run_compact_import(root, tmp_path):
    pptx = build_compact(tmp_path / "compact.pptx")
    dirs, _ = import_skeleton(root, pptx, tmp_path / "out")
    return [yaml.safe_load((d / "shapes.yaml").read_text(encoding="utf-8")) for d in dirs]


def test_content_right_under_the_title_is_guessed_as_the_compact_body(root, tmp_path, no_soffice):
    doc = run_compact_import(root, tmp_path)[0]
    guess = doc["frame_guess"]
    assert guess["frame"] == "standard" and guess["body"] == "compact" and "body_compact" in guess["reason"]
    assert doc["body_origin"] == [32, 88]


def test_compact_body_box_is_rebased_and_scaled_to_the_reference_size(root, tmp_path, no_soffice):
    shapes = run_compact_import(root, tmp_path)[0]["shapes"]
    card, pic = of_kind(shapes, "rounded")[0], of_kind(shapes, "picture")[0]
    assert card["box"] == [64, 96, 300, 100] and card["body_box"] == [32, 7.5, 300, 93.3]  # y、h 乘 560/600
    assert pic["body_box"] == [368, 7.5, 200, 130.7]
    assert of_kind(shapes, "textbox")[0]["body_box"][1] == -52.3  # 标题在 body 区之上：(32 - 88) × 560/600


def test_a_page_with_a_subtitle_row_keeps_the_standard_body(root, tmp_path, no_soffice):
    doc = run_compact_import(root, tmp_path)[1]
    assert doc["frame_guess"]["frame"] == "standard" and doc["frame_guess"]["body"] == "standard"
    assert doc["body_origin"] == [32, 128]
    assert of_kind(doc["shapes"], "rounded")[0]["body_box"] == [32, 12, 300, 100]


def test_content_beyond_the_compact_body_is_not_a_standard_page(root, tmp_path, no_soffice):
    guess = run_compact_import(root, tmp_path)[2]["frame_guess"]
    assert guess["frame"] == "none" and "1 个元素超出 body 区" in guess["reason"] and "body" not in guess


def test_14pt_text_maps_to_lead_when_regular_and_emphasis_when_bold(root, tmp_path, no_soffice):
    boxes = of_kind(run_compact_import(root, tmp_path)[3]["shapes"], "textbox")
    regular, bold = (b["text"][0] for b in boxes if b["text"][0]["size"] == 14)
    assert (regular["style"], bold["style"]) == ("lead", "emphasis")


def test_pictures_and_picture_placeholders_suggest_an_image_element(root, tmp_path, no_soffice):
    pic = of_kind(run_compact_import(root, tmp_path)[0]["shapes"], "picture")[0]
    assert pic["suggest"] == "image"
    (doc,), _ = run_import(root, tmp_path, [1])  # 另一份骨架：写着「图片」的灰色占位框
    holder = of_kind(doc["shapes"], "placeholder")[0]
    assert holder["label"] == "图片" and holder["suggest"] == "image"


@pytest.mark.parametrize("manifest", [
    "slides:\n  - slide: 1\n    purpose: 讲清楚问题\n  - slide: 3\n    purpose: 第三页的目的\n",
    "slides:\n  - purpose: 讲清楚问题\n  - purpose: 第二页\n  - purpose: 第三页的目的\n",
    "slides:\n  1: { purpose: 讲清楚问题 }\n  3: { purpose: 第三页的目的 }\n",
])
def test_purpose_is_copied_from_the_manifest_next_to_the_pptx(root, tmp_path, no_soffice, manifest):
    (tmp_path / "manifest.yaml").write_text(manifest, encoding="utf-8")
    docs, _ = run_import(root, tmp_path, [1, 3])
    assert [d["purpose"] for d in docs] == ["讲清楚问题", "第三页的目的"]


def test_no_manifest_means_no_purpose(root, tmp_path, no_soffice):
    (doc,), _ = run_import(root, tmp_path, [1])
    assert "purpose" not in doc


def test_without_soffice_warns_and_skips_original_png(root, tmp_path, no_soffice):
    docs, warnings = run_import(root, tmp_path, [1])
    assert any("找不到 soffice" in w for w in warnings)
    assert not (tmp_path / "out" / "slide-1" / "original.png").exists()


@pytest.mark.skipif(shutil.which("soffice") is None, reason="需要 LibreOffice (soffice)")
def test_original_png_is_rendered_per_selected_slide(root, tmp_path):
    pptx = build(tmp_path / "skeleton.pptx")
    dirs, warnings = import_skeleton(root, pptx, tmp_path / "out", [3])
    assert warnings == []
    with Image.open(dirs[0] / "original.png") as img:
        assert img.size == (1920, 1080)


def test_cli_import(root, tmp_path, monkeypatch, capsys, no_soffice):
    pptx = build(tmp_path / "skeleton.pptx")
    monkeypatch.chdir(root)
    assert main(["import", str(pptx), "--slide", "1", "3", "-o", str(tmp_path / "out")]) == 0
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [str(tmp_path / "out" / "slide-1"), str(tmp_path / "out" / "slide-3")]
    assert "警告  找不到 soffice" in captured.err
    assert main(["import", str(pptx), "--slide", "9", "-o", str(tmp_path / "out")]) == 1
    assert "超出范围" in capsys.readouterr().err
