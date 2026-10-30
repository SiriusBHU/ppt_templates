from pptx import Presentation
from pptx.oxml.ns import qn

from factories import deck_of, mini_template
from ppt_templates.components.arch_canvas import check
from ppt_templates.render import render_deck


def example_canvas():
    return {
        "canvas": [400, 200],
        "panels": [{"box": [0, 0, 400, 200], "fill": "surface_light"}],
        "shapes": [
            {"box": [20, 40, 120, 50], "fill": "bg", "line": "line", "text": "场景感知"},
            {"box": [240, 40, 120, 50], "fill": "highlight", "line": "accent", "text": "主动回收"},
        ],
        "texts": [{"box": [20, 120, 340, 30], "text": "原生架构说明", "style": "caption"}],
        "arrows": [{"points": [[140, 65], [190, 65], [190, 110], [240, 110]]}],
    }


def test_renders_native_editable_shapes_and_connectors(make_repo, tmp_path):
    template, example = mini_template()
    template["layout"] = [{"type": "component", "component": "arch-canvas", "box": [0, 0, 400, 200], "bind": "diagram"}]
    template["slots"]["required"] = ["title", "diagram"]
    template["slots"]["properties"] = {
        "title": {"type": "string", "maxLength": 14},
        "diagram": {"type": "object"},
    }
    example = {"title": "原生架构", "diagram": example_canvas()}
    repo = make_repo({"system.solution-flow": (template, example)})
    path = tmp_path / "canvas.pptx"
    render_deck(deck_of("system.solution-flow", example), repo).save(path)
    slide = Presentation(path).slides[0]
    assert not [shape for shape in slide.shapes if shape.shape_type == 13]
    texts = {shape.text for shape in slide.shapes if shape.has_text_frame}
    assert {"场景感知", "主动回收", "原生架构说明"} <= texts
    connectors = [shape for shape in slide.shapes if shape._element.tag == qn("p:cxnSp")]
    assert len(connectors) == 3
    assert connectors[-1]._element.xpath(".//a:tailEnd/@type") == ["triangle"]
    assert all(connector._element.xpath(".//a:tailEnd/@type") == [] for connector in connectors[:2])


def test_dash_draws_dashed_outline(make_repo, tmp_path):
    template, _ = mini_template()
    template["layout"] = [{"type": "component", "component": "arch-canvas", "box": [0, 0, 400, 200], "bind": "diagram"}]
    template["slots"]["required"] = ["title", "diagram"]
    template["slots"]["properties"] = {"title": {"type": "string", "maxLength": 14}, "diagram": {"type": "object"}}
    data = example_canvas()
    data["panels"][0].update(line="line", dash=True)
    example = {"title": "原生架构", "diagram": data}
    repo = make_repo({"system.solution-flow": (template, example)})
    path = tmp_path / "canvas.pptx"
    render_deck(deck_of("system.solution-flow", example), repo).save(path)
    panel = Presentation(path).slides[0].shapes[1]
    assert panel._element.xpath(".//a:prstDash/@val") == ["dash"]


def test_reports_elements_outside_reference_canvas():
    data = example_canvas()
    data["shapes"][0]["box"] = [390, 40, 20, 50]
    data["arrows"][0]["points"].append([420, 120])
    problems = check(data, (0, 0, 400, 200))
    assert (("shapes", 0, "box"), "超出参考画布 400×200") in problems
    assert (("arrows", 0, "points", 4), "超出参考画布 400×200") in problems
