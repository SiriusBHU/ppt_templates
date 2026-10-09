import pytest
from pptx import Presentation

from ppt_templates.cli import main
from ppt_templates.errors import PptError
from ppt_templates.render import render_deck
from ppt_templates.slots import fill_defaults, prepare_pages


@pytest.fixture
def pptx_path(deck, root, tmp_path):
    path = tmp_path / "out.pptx"
    render_deck(deck, root).save(path)
    return path


def test_render_example_reopens_with_one_slide_of_16_9(pptx_path):
    prs = Presentation(pptx_path)
    assert (prs.slide_width, prs.slide_height) == (12192000, 6858000)
    assert len(prs.slides) == 1


def test_render_contains_title_and_every_module_name(deck, pptx_path):
    data = deck["pages"][0]["data"]
    texts = {sh.text_frame.text for sh in Presentation(pptx_path).slides[0].shapes if sh.has_text_frame}
    assert f"{data['title']}　{data['title_suffix']}" in texts
    assert data["takeaway"] in texts
    assert "1" not in texts  # 不画页码
    for layer in data["layers"]:
        assert layer["name"] in texts
        for module in layer["modules"]:
            assert module["name"] in texts


def test_every_run_has_cjk_and_cs_fonts(pptx_path):
    slide = Presentation(pptx_path).slides[0]
    runs = slide._element.xpath(".//a:r")
    assert runs
    for tag in ("latin", "ea", "cs"):
        assert slide._element.xpath(f".//a:r/a:rPr/a:{tag}/@typeface") == ["微软雅黑"] * len(runs)


def _shape_with_text(pptx_path, text):
    return next(sh for sh in Presentation(pptx_path).slides[0].shapes if sh.has_text_frame and sh.text_frame.text == text)


def test_frame_decorations_have_no_outline_and_no_shadow(pptx_path):
    decoration = Presentation(pptx_path).slides[0].shapes[0]  # 标题区下的分隔线：先于其他内容绘制
    assert (decoration.left, decoration.top, decoration.width, decoration.height) == (32 * 9525, 116 * 9525, 1216 * 9525, 9525)
    assert decoration._element.xpath("./p:spPr/a:ln/a:noFill")
    assert decoration._element.xpath("./p:spPr/a:effectLst")


def test_positions_follow_frame_regions_and_body_origin(pptx_path):
    title = _shape_with_text(pptx_path, "检查点加速方案　引入近计算缓存")
    assert (title.left, title.top, title.width, title.height) == (32 * 9525, 32 * 9525, 1216 * 9525, 40 * 9525)
    label = _shape_with_text(pptx_path, "接入层")  # layered-arch 的 box 原点 = body 左上角 (32, 128)
    assert (label.left, label.top, label.width) == (32 * 9525, 128 * 9525, 120 * 9525)


def test_margins_are_equal_on_all_sides(root):
    from ppt_templates.loader import load_style
    frame = load_style(root, "default")["frame"]
    x, y, w, h = frame["body"]["box"]
    assert frame["title"]["box"][:2] == [32, 32]
    assert (x, 1280 - x - w, 720 - y - h) == (32, 32, 32)


def test_title_and_suffix_share_one_line_with_24_and_18_pt(pptx_path):
    runs = _shape_with_text(pptx_path, "检查点加速方案　引入近计算缓存").text_frame.paragraphs[0].runs
    assert [(r.font.size.pt, bool(r.font.bold)) for r in runs] == [(24, True), (18, False)]


def test_title_without_suffix_is_a_single_run(deck, root, tmp_path):
    del deck["pages"][0]["data"]["title_suffix"]
    path = tmp_path / "t.pptx"
    render_deck(deck, root).save(path)
    runs = _shape_with_text(path, "检查点加速方案").text_frame.paragraphs[0].runs
    assert len(runs) == 1 and runs[0].font.size.pt == 24


def test_every_font_size_is_in_the_allowed_set(pptx_path):
    sizes = {r.font.size.pt for sh in Presentation(pptx_path).slides[0].shapes if sh.has_text_frame
             for p in sh.text_frame.paragraphs for r in p.runs}
    assert sizes <= {24, 18, 14, 12, 10, 9, 8}


def test_highlighted_module_style(pptx_path):
    hot, plain = _shape_with_text(pptx_path, "检查点加速"), _shape_with_text(pptx_path, "元数据服务")
    assert hot.line.width == 19050 and plain.line.width == 9525
    assert str(hot.line.color.rgb) == "EA7317" and str(hot.fill.fore_color.rgb) == "FFF1E6"
    run = hot.text_frame.paragraphs[0].runs[0]
    assert run.font.bold and str(run.font.color.rgb) == "EA7317"
    assert not plain.text_frame.paragraphs[0].runs[0].font.bold


def test_legend_only_when_a_module_is_highlighted(deck, root, tmp_path):
    def texts(d):
        path = tmp_path / "t.pptx"
        render_deck(d, root).save(path)
        return {sh.text_frame.text for sh in Presentation(path).slides[0].shapes if sh.has_text_frame}

    assert "本次新增 / 改动" in texts(deck)
    for layer in deck["pages"][0]["data"]["layers"]:
        for module in layer["modules"]:
            module["highlight"] = False
    assert "本次新增 / 改动" not in texts(deck)


def test_title_over_limit_is_rejected_with_json_pointer(deck, root):
    deck["pages"][0]["data"]["title"] = "标" * 30
    with pytest.raises(PptError) as exc:
        render_deck(deck, root)
    assert "第 1 页 system.solution-layered-arch  /pages/0/data/title  长度 30，超过上限 14" in str(exc.value)


def test_nested_error_pointer_and_page_number(deck, root):
    deck["pages"].append({"template": deck["pages"][0]["template"], "data": {"title": "x", "layers": []}})
    with pytest.raises(PptError) as exc:
        prepare_pages(deck, root)
    assert "第 2 页 system.solution-layered-arch  /pages/1/data/layers  共 0 项，低于下限 3" in str(exc.value)
    assert "/pages/1/data  缺少必填字段 design_points、benefits" in str(exc.value)


def test_unknown_template_is_reported(deck, root):
    deck["pages"][0]["template"] = "system.nope"
    with pytest.raises(PptError, match="第 1 页 system.nope  /pages/0/template"):
        prepare_pages(deck, root)


def test_fill_defaults_recurses_into_arrays_and_objects(deck, root):
    template, data = prepare_pages(deck, root)[0]
    modules = [m for layer in data["layers"] for m in layer["modules"]]
    assert all("highlight" in m for m in modules)
    assert modules[0]["highlight"] is False
    # 不修改调用方传入的数据
    assert "highlight" not in deck["pages"][0]["data"]["layers"][0]["modules"][0]
    assert fill_defaults({"type": "object", "properties": {"a": {"default": 1}}}, {}) == {"a": 1}


def test_cli_render_writes_pptx(deck, tmp_path, monkeypatch, root):
    import yaml

    deck_path = tmp_path / "deck.yaml"
    deck_path.write_text(yaml.safe_dump(deck, allow_unicode=True), encoding="utf-8")
    monkeypatch.chdir(root)
    assert main(["render", str(deck_path), "-o", str(tmp_path / "o" / "out.pptx")]) == 0
    assert len(Presentation(tmp_path / "o" / "out.pptx").slides) == 1


def test_cli_exits_nonzero_and_prints_pointer_on_invalid_data(deck, tmp_path, monkeypatch, root, capsys):
    import yaml

    deck["pages"][0]["data"]["title"] = "标" * 30
    deck_path = tmp_path / "deck.yaml"
    deck_path.write_text(yaml.safe_dump(deck, allow_unicode=True), encoding="utf-8")
    monkeypatch.chdir(root)
    assert main(["render", str(deck_path), "-o", str(tmp_path / "out.pptx")]) == 1
    assert "/pages/0/data/title" in capsys.readouterr().err
    assert not (tmp_path / "out.pptx").exists()


def test_deck_structure_errors_are_reported(root):
    with pytest.raises(PptError, match="deck 结构错误"):
        render_deck({"pages": []}, root)
