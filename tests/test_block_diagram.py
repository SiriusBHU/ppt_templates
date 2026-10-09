import pytest
import yaml
from pptx import Presentation
from pptx.oxml.ns import qn

from factories import deck_of, diagram_template
from ppt_templates.errors import PptError
from ppt_templates.render import render_deck
from ppt_templates.slots import prepare_pages
from ppt_templates.validate import validate_repo


def test_nodes_and_arrow_connectors(make_repo, tmp_path):
    template, example = diagram_template()
    repo = make_repo({"system.solution-flow": (template, example)})
    assert validate_repo(repo).errors == []
    path = tmp_path / "d.pptx"
    render_deck(deck_of("system.solution-flow", example), repo).save(path)
    shapes = list(Presentation(path).slides[0].shapes)
    node = {sh.text_frame.text: sh for sh in shapes if sh.has_text_frame}
    conns = [sh for sh in shapes if sh._element.tag == qn("p:cxnSp")]
    assert len(conns) == 3
    gpu, nvme, store, meta = node["训练进程"], node["本地 NVMe"], node["存储集群"], node["元数据服务"]
    first, _, last = conns
    assert abs(first.begin_x - (gpu.left + gpu.width)) <= 1 and abs(first.end_x - nvme.left) <= 1      # 水平：右 → 左
    assert abs(last.begin_y - (store.top + store.height)) <= 1 and abs(last.end_y - meta.top) <= 1     # 垂直：下 → 上
    assert all(c._element.xpath(".//a:tailEnd/@type") == ["triangle"] for c in conns)
    assert "同步写" in node and "异步下刷" in node
    assert str(nvme.fill.fore_color.rgb) == "FFF1E6"


FLOW = "system.solution-flow"


def _prepare_error(repo, example) -> str:
    with pytest.raises(PptError) as exc:
        prepare_pages(deck_of(FLOW, example), repo)
    return str(exc.value)


@pytest.mark.parametrize("mutate, where, message", [
    (lambda f: f["edges"].append({"from": "gpu", "to": "ghost"}), "edges/3/to", "连线引用了不存在的节点: ghost"),
    (lambda f: f["nodes"].append({"id": "x", "name": "重叠", "pos": [0, 0]}), "nodes/4/pos", "节点位置重复: [0, 0]"),
    (lambda f: f["nodes"].append({"id": "gpu", "name": "重复", "pos": [1, 0]}), "nodes/4/id", "节点 id 重复: gpu"),
])
def test_bad_references_are_reported_with_page_and_pointer(make_repo, mutate, where, message):
    template, example = diagram_template()
    mutate(example["flow"])
    repo = make_repo({FLOW: (template, example)})
    assert f"第 1 页 {FLOW}  /pages/0/data/flow/{where}  {message}（组件 block-diagram）" in _prepare_error(repo, example)
    assert f"templates/system/solution-flow/example.yaml  /flow/{where}  {message}（组件 block-diagram）" in validate_repo(repo).errors


@pytest.mark.parametrize("nodes, expected", [
    ([("a", [0, 0]), ("b", [0, 20])], "1 行 21 列的节点只有 -11×400 px，小于下限 40×24"),     # 宽度为负
    ([(f"n{i}", [i, 0]) for i in range(12)], "12 行 1 列的节点只有 1216×4 px，小于下限 40×24"),  # 高度只剩 4px
])
def test_nodes_smaller_than_minimum_are_rejected(make_repo, nodes, expected):
    template, example = diagram_template()
    example["flow"] = {"nodes": [{"id": i, "name": i, "pos": pos} for i, pos in nodes]}
    repo = make_repo({FLOW: (template, example)})
    assert f"/pages/0/data/flow/nodes  {expected}，请减少行列数（组件 block-diagram）" in _prepare_error(repo, example)
    assert any(f"example.yaml  /flow/nodes  {expected}" in e for e in validate_repo(repo).errors)


def test_render_rechecks_node_size_against_the_actual_body_area(make_repo):
    template, example = diagram_template()
    repo = make_repo({FLOW: (template, example)})
    style_path = repo / "styles" / "default" / "style.yaml"
    style = yaml.safe_load(style_path.read_text(encoding="utf-8"))
    style["frame"]["body"]["box"] = [32, 128, 200, 560]    # body 区比参考尺寸窄得多
    style_path.write_text(yaml.safe_dump(style, allow_unicode=True), encoding="utf-8")
    with pytest.raises(PptError, match="组件 block-diagram  /nodes  2 行 3 列的节点只有"):
        render_deck(deck_of(FLOW, example), repo)
