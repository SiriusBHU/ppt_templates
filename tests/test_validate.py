import pytest

from factories import mini_template
from ppt_templates.taxonomy import check_taxonomy
from ppt_templates.validate import validate_repo

F = "templates/common/summary-note/template.yaml"


def test_taxonomy_ids_must_be_single_lowercase_words_and_unique():
    raw = {
        "topics": [{"id": "system", "name": "系统"}, {"id": "system", "name": "重复"}],
        "roles": [{"id": "next-steps", "name": "下一步"}],
    }
    assert check_taxonomy(raw) == [
        "taxonomy.yaml  /topics/1/id  重复的 id system",
        "taxonomy.yaml  /roles/0/id  'next-steps' 必须是单个小写英文单词",
    ]


def test_mini_template_is_valid(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    assert validate_repo(repo).errors == []


@pytest.mark.parametrize("overrides, expected", [
    ({"id": "common.other"}, "/id  应为 common.summary-note（由目录决定），实际是 common.other"),
    ({"roles": ["nope"]}, "/roles/0  页功能 nope 不在 taxonomy.yaml 中"),
    ({"roles": ["risk"]}, "/roles/0  目录名 summary-note 必须以主页功能 risk- 开头"),
    ({"density": "read"}, "/density  目录名以 -read 结尾，当且仅当 density: read"),
    ({"also_fits": ["common"]}, "/also_fits/0  不能包含模板自己的主题"),
    ({"also_fits": ["galaxy"]}, "/also_fits/0  主题 galaxy 不在 taxonomy.yaml 中"),
    ({"level": "module"}, "/level  level 只用于 hardware、software、system 主题"),
    ({"layout": [{"type": "text", "box": [0, 0, 10, 10], "bind": "note", "style": "body", "size": 13}]},
     "/layout/0  不允许的字段 size"),
    ({"frame": "wide"}, "/frame  取值 wide 不在可选范围 ['standard', 'none']"),
])
def test_template_metadata_rules(make_repo, overrides, expected):
    repo = make_repo({"common.summary-note": mini_template(**overrides)})
    assert f"{F}  {expected}" in validate_repo(repo).errors


def test_unknown_topic_directory(make_repo):
    repo = make_repo({"galaxy.summary-note": mini_template(id="galaxy.summary-note")})
    assert "templates/galaxy/summary-note/template.yaml  /  主题目录 galaxy 不在 taxonomy.yaml 中" in validate_repo(repo).errors


def test_slots_must_be_an_object_schema(make_repo):
    repo = make_repo({"common.summary-note": mini_template(slots={"type": "array"})})
    assert f"{F}  /slots/type  顶层必须是 type: object" in validate_repo(repo).errors


def test_missing_example_is_an_error_and_missing_preview_a_warning(make_repo):
    template, _ = mini_template()
    repo = make_repo({"common.summary-note": (template, None)})
    report = validate_repo(repo)
    assert "templates/common/summary-note  缺少 example.yaml" in report.errors
    assert report.warnings == ["templates/common/summary-note  缺少 preview.png（运行 uv run ppt preview common.summary-note --write）"]


def _errors(make_repo, **overrides):
    repo = make_repo({"common.summary-note": mini_template(**overrides)})
    return [e.removeprefix(f"{F}  ") for e in validate_repo(repo).errors if e.startswith(F)]


def _slots(**extra):
    props = {"title": {"type": "string", "maxLength": 14}, "note": {"type": "string", "maxLength": 60}, **extra}
    return {"type": "object", "required": ["title"], "properties": props}


NOTE = {"type": "text", "box": [0, 0, 600, 80], "bind": "note", "style": "body"}


def test_unbound_slot(make_repo):
    assert "/slots/properties/extra  槽位没有被 layout 渲染" in _errors(
        make_repo, slots=_slots(extra={"type": "string"}))


def test_bind_to_missing_slot(make_repo):
    assert "/layout/1/bind  槽位 nope 不存在" in _errors(
        make_repo, layout=[NOTE, {**NOTE, "bind": "nope"}])


def test_layout_cannot_bind_frame_slots(make_repo):
    assert "/layout/1/bind  title 由页框渲染，layout 不能再绑定" in _errors(
        make_repo, layout=[NOTE, {**NOTE, "bind": "title"}])


def test_standard_frame_requires_title(make_repo):
    slots = _slots()
    slots["required"] = ["note"]
    assert "/slots/required  frame: standard 的模板必须把 title 列为必填" in _errors(make_repo, slots=slots)


def test_frame_slots_must_be_strings(make_repo):
    assert "/slots/properties/takeaway  页框槽位必须是 type: string" in _errors(
        make_repo, slots=_slots(takeaway={"type": "array"}))


def test_unknown_tokens(make_repo):
    errs = _errors(make_repo, layout=[{**NOTE, "style": "h3", "color": "red"},
                                      {"type": "shape", "box": [0, 100, 10, 10], "fill": "blue"}])
    assert "/layout/0/style  未知文字样式 token h3" in errs
    assert "/layout/0/color  未知颜色 token red" in errs
    assert "/layout/1/fill  未知颜色 token blue" in errs


def test_duplicate_binding(make_repo):
    assert "/layout/1/bind  槽位 note 被重复绑定" in _errors(make_repo, layout=[NOTE, NOTE])


def test_bind_type_must_match_element(make_repo):
    slots = _slots(items={"type": "array", "items": {"type": "string"}})
    errs = _errors(make_repo, slots=slots, layout=[
        NOTE,
        {"type": "text", "box": [0, 100, 600, 80], "bind": "items", "style": "body"},
        {"type": "grid", "box": [0, 200, 600, 80], "bind": "items", "columns": 2, "item": []},
    ])
    assert "/layout/1/bind  text 只能绑定 string 槽位，实际是 array" in errs
    assert "/layout/2/bind  grid 绑定的数组必须声明 maxItems" in errs


def test_unknown_component(make_repo):
    assert "/layout/1/component  未知组件 pie" in _errors(
        make_repo, layout=[NOTE, {"type": "component", "component": "pie", "box": [0, 100, 10, 10], "bind": "note"}])


def test_component_slot_type_must_match(make_repo):
    errs = _errors(make_repo, layout=[
        NOTE, {"type": "component", "component": "layered-arch", "box": [0, 100, 600, 300], "bind": "title"}])
    assert "/layout/1/bind  组件 layered-arch 需要 array 类型的槽位，实际是 string" in errs


def test_frame_none_renders_title_through_layout(make_repo):
    layout = [{"type": "text", "box": [32, 32, 1216, 40], "bind": "title", "style": "title"},
              {"type": "text", "box": [32, 100, 1216, 80], "bind": "note", "style": "body"}]
    assert _errors(make_repo, frame="none", layout=layout) == []


def test_element_outside_body_area(make_repo):
    assert "/layout/0/box  超出 body 区 1216×560" in _errors(
        make_repo, layout=[{**NOTE, "box": [0, 0, 1300, 80]}])


def test_grid_item_must_fit_smallest_cell(make_repo):
    slots = _slots(points={"type": "array", "maxItems": 6, "items": {"type": "string"}})
    grid = {"type": "grid", "box": [0, 100, 600, 100], "bind": "points", "columns": 3, "gap": 10,
            "item": [{"type": "text", "box": [0, 0, "100%", 60], "bind": ".", "style": "body"}]}
    assert "/layout/1/item/0/box  按 maxItems=6 计算的单元格 193×45 放不下" in _errors(
        make_repo, slots=slots, layout=[NOTE, grid])


def test_example_must_pass_slots(make_repo):
    template, example = mini_template()
    example["note"] = "长" * 61
    repo = make_repo({"common.summary-note": (template, example)})
    assert "templates/common/summary-note/example.yaml  /note  长度 61，超过上限 60" in validate_repo(repo).errors


def test_component_data_in_example_must_pass_component_schema(make_repo):
    slots = _slots(layers={"type": "array", "items": {"type": "object"}})
    layout = [NOTE, {"type": "component", "component": "layered-arch", "box": [0, 100, 800, 400], "bind": "layers"}]
    template, example = mini_template(slots=slots, layout=layout)
    example["layers"] = [{"name": "接入层"}]
    repo = make_repo({"common.summary-note": (template, example)})
    assert ("templates/common/summary-note/example.yaml  /layers/0  缺少必填字段 modules（组件 layered-arch）"
            in validate_repo(repo).errors)


BULLETS = {"type": "bullets", "box": [0, 100, 600, 100], "bind": "points", "style": "body"}
BULLETS_MESSAGE = "bullets 只能绑定 string 数组，或含 string 字段 text 的对象数组"
LEVEL_MESSAGE = "bullets 的 level 必须是 type: integer 且 minimum: 0"


def _bullet_items(**props):
    return {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}, **props}}


@pytest.mark.parametrize("items, expected", [
    ({"type": "object", "properties": {"text": {"type": "string"}}}, BULLETS_MESSAGE),                # text 非必填
    ({"type": "object", "required": ["text"], "properties": {"text": {"type": "integer"}}}, BULLETS_MESSAGE),
    (_bullet_items(level={"type": "number", "minimum": 0}), LEVEL_MESSAGE),                           # 0.5 级
    (_bullet_items(level={"type": "integer"}), LEVEL_MESSAGE),                                        # 可以是负数
    (_bullet_items(level={"type": "integer", "minimum": -1}), LEVEL_MESSAGE),
    (_bullet_items(level=True), LEVEL_MESSAGE),
    (_bullet_items(level={"type": "integer", "minimum": 0, "maximum": 2}), None),
    ({"type": "string"}, None),
])
def test_bullets_item_schema(make_repo, items, expected):
    slots = _slots(points={"type": "array", "maxItems": 6, "items": items})
    errs = _errors(make_repo, slots=slots, layout=[NOTE, BULLETS])
    assert errs == ([] if expected is None else [f"/layout/1/bind  {expected}"])


@pytest.mark.parametrize("component, slot_type, props, expected", [
    ("table", "object", {"first_column_width": "200"}, "/props/first_column_width  类型应为 number"),
    ("table", "object", {"first_column_width": 0}, "/props/first_column_width  取值 0，必须大于 0"),
    ("table", "object", {"width": 200}, "/props  不允许的字段 width"),
    ("layered-arch", "array", {"legend": 1}, "/props/legend  类型应为 string"),
    ("block-diagram", "object", {"legend": "x"}, "/props  不允许的字段 legend"),
])
def test_component_props_are_validated(make_repo, component, slot_type, props, expected):
    layout = [NOTE, {"type": "component", "component": component, "box": [0, 100, 600, 300], "bind": "c", "props": props}]
    assert f"/layout/1{expected}（组件 {component}）" in _errors(
        make_repo, slots=_slots(c={"type": slot_type}), layout=layout)


def test_valid_component_props_pass(make_repo):
    layout = [NOTE, {"type": "component", "component": "table", "box": [0, 100, 600, 300], "bind": "c",
                     "props": {"first_column_width": 120.5}}]
    errs = _errors(make_repo, slots=_slots(c={"type": "object"}), layout=layout)
    assert not [e for e in errs if "props" in e]


@pytest.mark.parametrize("slots, layout, expected", [
    (_slots(note=True), [NOTE], "/layout/0/bind  槽位必须是对象 schema"),
    (_slots(takeaway=False), [NOTE], "/slots/properties/takeaway  页框槽位必须是 type: string"),
    (_slots(points={"type": "array", "maxItems": 3, "items": True}), [NOTE, BULLETS], f"/layout/1/bind  {BULLETS_MESSAGE}"),
    (_slots(points=True), [NOTE, {"type": "grid", "box": [0, 100, 600, 100], "bind": "points", "columns": 2, "item": []}],
     "/layout/1/bind  槽位必须是对象 schema"),
    (_slots(points={"type": "array", "maxItems": 3, "items": True}),
     [NOTE, {"type": "grid", "box": [0, 100, 600, 100], "bind": "points", "columns": 2,
             "item": [{"type": "text", "box": [0, 0, 100, 20], "bind": ".", "style": "body"}]}],
     "/layout/1/item/0/bind  text 只能绑定 string 槽位，实际是 None"),
])
def test_boolean_subschemas_are_reported_not_crashed(make_repo, slots, layout, expected):
    assert expected in _errors(make_repo, slots=slots, layout=layout)


def test_grid_cells_must_be_positive(make_repo):
    slots = _slots(points={"type": "array", "maxItems": 6, "items": {"type": "string"}})
    grid = {"type": "grid", "box": [0, 100, 100, 100], "bind": "points", "columns": 3, "gap": 60,
            "item": [{"type": "text", "box": [0, 0, 10, 10], "bind": ".", "style": "body"}]}
    errs = _errors(make_repo, slots=slots, layout=[NOTE, grid])
    assert "/layout/1/box  按 maxItems=6 计算的单元格 -7×20 不是正数（gap 过大或 box 过小）" in errs
    assert not [e for e in errs if "/item/" in e]


def test_grid_item_with_negative_width_does_not_fit(make_repo):
    slots = _slots(points={"type": "array", "maxItems": 3, "items": {"type": "string"}})
    grid = {"type": "grid", "box": [0, 100, 40, 100], "bind": "points", "columns": 3, "gap": 5,
            "item": [{"type": "text", "box": [0, 0, "100%-14", 20], "bind": ".", "style": "body"}]}
    assert "/layout/1/item/0/box  按 maxItems=3 计算的单元格 10×100 放不下" in _errors(
        make_repo, slots=slots, layout=[NOTE, grid])


def _points_slots(max_items=6):
    return _slots(points={"type": "array", "maxItems": max_items, "items": {"type": "string"}})


def _points_grid(**grid):
    return {"type": "grid", "box": [0, 100, 600, 130], "bind": "points", "columns": 3, "gap": 10,
            "item": [{"type": "text", "box": [0, 0, "100%", 20], "bind": ".", "style": "body"}], **grid}


def test_grid_columns_is_a_maximum_for_geometry(make_repo):
    # maxItems=2、columns=4 → 最小单元格按 2 列算：宽 295；item 宽 250 放得下，350 放不下
    grid = _points_grid(columns=4, item=[{"type": "text", "box": [0, 0, 250, 20], "bind": ".", "style": "body"}])
    assert _errors(make_repo, slots=_points_slots(2), layout=[NOTE, grid]) == []


def test_grid_item_too_wide_for_effective_columns(make_repo):
    grid = _points_grid(columns=4, item=[{"type": "text", "box": [0, 0, 350, 20], "bind": ".", "style": "body"}])
    assert "/layout/1/item/0/box  按 maxItems=2 计算的单元格 295×130 放不下" in _errors(
        make_repo, slots=_points_slots(2), layout=[NOTE, grid])


def test_row_height_that_fits_the_box_height_is_valid(make_repo):
    # maxItems=6、3 列 → 2 行：2×60 + 10 = 130 刚好放下
    assert _errors(make_repo, slots=_points_slots(), layout=[NOTE, _points_grid(row_height=60)]) == []


def test_row_height_rows_must_fit_box_height(make_repo):
    # row_height 70 → 2×70 + 10 = 150 > 130
    assert "/layout/1/row_height  按 maxItems=6 排 2 行，需要 150px（2×70 + 间距 10），超过 box 高 130px" in _errors(
        make_repo, slots=_points_slots(), layout=[NOTE, _points_grid(row_height=70)])


def test_row_height_item_must_fit_min_cell(make_repo):
    item = [{"type": "text", "box": [0, 0, "100%", 70], "bind": ".", "style": "body"}]
    assert "/layout/1/item/0/box  按 maxItems=6 计算的单元格 193×60 放不下" in _errors(
        make_repo, slots=_points_slots(), layout=[NOTE, _points_grid(row_height=60, item=item)])


def test_row_height_must_be_positive_number(make_repo):
    assert "/layout/1/row_height  取值 0，必须大于 0" in _errors(
        make_repo, slots=_points_slots(), layout=[NOTE, _points_grid(row_height=0)])


def test_when_must_point_to_an_existing_slot(make_repo):
    shape = {"type": "shape", "box": [0, 100, 10, 10], "fill": "accent"}
    errs = _errors(make_repo, slots=_points_slots(), layout=[
        NOTE, {**shape, "when": "nope"}, {**shape, "when": "note"},
        _points_grid(item=[{**shape, "box": [0, 0, 10, 10], "when": "."}, {**shape, "box": [0, 0, 10, 10], "when": "gone"}])])
    assert "/layout/1/when  槽位 nope 不存在" in errs
    assert "/layout/3/item/1/when  槽位 gone 不存在" in errs
    assert not [e for e in errs if "/layout/2/" in e or "/layout/3/item/0/" in e]


def test_when_must_be_a_string(make_repo):
    assert "/layout/1/when  类型应为 string" in _errors(
        make_repo, layout=[NOTE, {"type": "shape", "box": [0, 100, 10, 10], "fill": "accent", "when": 1}])


def test_when_is_checked_on_every_element_type(make_repo):
    errs = _errors(make_repo, layout=[
        {**NOTE, "when": "nope"},
        {"type": "bullets", "box": [0, 100, 10, 10], "bind": "note", "style": "body", "when": "nope"},
        {"type": "component", "component": "table", "box": [0, 100, 10, 10], "bind": "note", "when": "nope"}])
    assert [e for e in errs if e.endswith("/when  槽位 nope 不存在")] == [
        f"/layout/{i}/when  槽位 nope 不存在" for i in range(3)]


LEVEL = {"type": "string", "enum": ["高", "中", "低"]}
LEVEL_TEXT = {"type": "text", "box": [0, 100, 100, 20], "bind": "level", "style": "body"}
LEVEL_SHAPE = {"type": "shape", "box": [0, 120, 20, 20], "fill": "surface", "by": "level"}


def test_value_based_colors_pass_validation(make_repo):
    layout = [NOTE, {**LEVEL_TEXT, "color_map": {"高": "highlight_strong", "低": "accent"}},
              {**LEVEL_SHAPE, "fill_map": {"高": "highlight"}, "line_map": {"高": "highlight_strong"}}]
    assert _errors(make_repo, slots=_slots(level=LEVEL), layout=layout) == []


def test_color_map_values_must_be_color_tokens(make_repo):
    layout = [NOTE, {**LEVEL_TEXT, "color_map": {"高": "red"}},
              {**LEVEL_SHAPE, "fill_map": {"高": "blue"}, "line_map": {"中": "green"}}]
    errs = _errors(make_repo, slots=_slots(level=LEVEL), layout=layout)
    assert "/layout/1/color_map/高  未知颜色 token red" in errs
    assert "/layout/2/fill_map/高  未知颜色 token blue" in errs
    assert "/layout/2/line_map/中  未知颜色 token green" in errs


def test_by_must_point_to_an_existing_slot(make_repo):
    layout = [NOTE, {**LEVEL_SHAPE, "by": "nope", "fill_map": {"高": "highlight"}}]
    assert "/layout/1/by  槽位 nope 不存在" in _errors(make_repo, slots=_slots(level=LEVEL), layout=layout)


def test_shape_maps_require_by(make_repo):
    shape = {"type": "shape", "box": [0, 120, 20, 20], "fill": "surface"}
    errs = _errors(make_repo, layout=[NOTE, {**shape, "fill_map": {"高": "highlight"}}, {**shape, "line_map": {"高": "line"}}])
    for i in (1, 2):
        assert f"/layout/{i}/by  fill_map / line_map 必须用 by 指明按哪个槽位取色" in errs


def test_text_color_map_needs_a_value_to_match(make_repo):
    fixed = {"type": "text", "box": [0, 100, 100, 20], "value": "固定文字", "style": "body", "color_map": {"高": "accent"}}
    assert "/layout/1/color_map  color_map 必须配合 bind 或 by，才知道按哪个值取色" in _errors(make_repo, layout=[NOTE, fixed])


def test_text_color_map_with_value_and_by_is_valid(make_repo):
    fixed = {"type": "text", "box": [0, 100, 100, 20], "value": "固定文字", "style": "body", "color_map": {"高": "accent"}}
    assert _errors(make_repo, slots=_slots(level=LEVEL), layout=[NOTE, {**fixed, "by": "level"}, LEVEL_TEXT]) == []


@pytest.mark.parametrize("element, bad", [
    ({**LEVEL_TEXT, "color_map": {"高": "accent", "紧急": "accent"}}, "color_map/紧急"),
    ({**LEVEL_SHAPE, "fill_map": {"紧急": "highlight"}}, "fill_map/紧急"),
    ({**LEVEL_SHAPE, "line_map": {"紧急": "highlight"}}, "line_map/紧急"),
    ({**LEVEL_TEXT, "bind": "note", "by": "level", "color_map": {"紧急": "accent"}}, "color_map/紧急"),
])
def test_map_keys_must_be_in_the_slot_enum(make_repo, element, bad):
    errs = _errors(make_repo, slots=_slots(level=LEVEL), layout=[NOTE, element])
    assert f"/layout/1/{bad}  键 紧急 不在槽位 level 的可选取值 ['高', '中', '低'] 内" in errs


def test_map_keys_are_compared_as_strings_against_the_enum(make_repo):
    slots = _slots(n={"type": "integer", "enum": [1, 2]})
    element = {"type": "text", "box": [0, 100, 100, 20], "bind": "note", "style": "body", "by": "n",
               "color_map": {"2": "accent", 3: "accent"}}
    errs = _errors(make_repo, slots=slots, layout=[element, {**LEVEL_TEXT, "bind": "n"}])
    assert [e for e in errs if "color_map" in e] == ["/layout/0/color_map/3  键 3 不在槽位 n 的可选取值 [1, 2] 内"]


INDEX = {"type": "text", "box": [0, 0, 20, 20], "bind": "#", "style": "body"}
ITEM = {"type": "text", "box": [30, 0, 100, 20], "bind": ".", "style": "body"}


def test_index_bind_in_a_grid_item_is_not_a_slot_binding(make_repo):
    # "#" 不对应槽位：同一个 item 里可以用多次，不会报「重复绑定」，也不影响槽位是否被渲染
    grid = _points_grid(item=[INDEX, {**INDEX, "box": [140, 0, 20, 20]}, ITEM])
    assert _errors(make_repo, slots=_points_slots(), layout=[NOTE, grid]) == []


def test_index_bind_outside_a_grid_item_is_an_error(make_repo):
    assert "/layout/1/bind  # 只能用在 grid 的 item 内" in _errors(make_repo, layout=[NOTE, INDEX])


@pytest.mark.parametrize("kind, element", [
    ("bullets", {"type": "bullets", "box": [0, 0, 100, 20], "bind": "#", "style": "body"}),
    ("grid", {"type": "grid", "box": [0, 0, 100, 20], "bind": "#", "columns": 1, "item": []}),
])
def test_index_bind_only_binds_to_text(make_repo, kind, element):
    errs = _errors(make_repo, slots=_points_slots(), layout=[NOTE, _points_grid(item=[element])])
    assert f"/layout/1/item/0/bind  # 只能绑定给 text，实际是 {kind}" in errs


@pytest.mark.parametrize("kind, valid", [("oval", True), ("rounded", True), ("star", False)])
def test_shape_kinds(make_repo, kind, valid):
    shape = {"type": "shape", "box": [0, 100, 10, 10], "fill": "accent", "shape": kind}
    errs = _errors(make_repo, layout=[NOTE, shape])
    assert (errs == []) is valid
    assert valid or any("取值 star 不在可选范围 ['rect', 'rounded', 'oval']" in e for e in errs)


RUNS = {"type": "text", "box": [0, 100, 600, 40], "style": "body", "runs": [{"bind": "extra", "style": "body_strong"}, {"value": "："}]}


def test_run_binds_count_as_rendered_slots(make_repo):
    assert _errors(make_repo, slots=_slots(extra={"type": "string"}), layout=[NOTE, RUNS]) == []


def test_run_bind_to_a_missing_slot_or_a_non_string_slot(make_repo):
    slots = _slots(items={"type": "array", "items": {"type": "string"}}, extra={"type": "string"})
    runs = {**RUNS, "runs": [{"bind": "nope"}, {"bind": "items"}, {"bind": "extra"}]}
    errs = _errors(make_repo, slots=slots, layout=[NOTE, runs])
    assert "/layout/1/runs/0/bind  槽位 nope 不存在" in errs
    assert "/layout/1/runs/1/bind  text 只能绑定 string 槽位，实际是 array" in errs
    assert not [e for e in errs if "/runs/2/" in e]


def test_run_bind_duplicates_a_top_level_binding(make_repo):
    errs = _errors(make_repo, layout=[NOTE, {**RUNS, "runs": [{"bind": "note"}]}])
    assert "/layout/1/runs/0/bind  槽位 note 被重复绑定" in errs


def test_run_bind_cannot_use_frame_slots(make_repo):
    assert "/layout/1/runs/0/bind  title 由页框渲染，layout 不能再绑定" in _errors(
        make_repo, layout=[NOTE, {**RUNS, "runs": [{"bind": "title"}]}])


def test_run_tokens_must_exist(make_repo):
    runs = {**RUNS, "runs": [{"value": "x", "style": "h3", "color": "red"}]}
    errs = _errors(make_repo, layout=[NOTE, runs])
    assert "/layout/1/runs/0/style  未知文字样式 token h3" in errs
    assert "/layout/1/runs/0/color  未知颜色 token red" in errs


def test_runs_color_map_needs_by(make_repo):
    errs = _errors(make_repo, layout=[NOTE, {**RUNS, "runs": [{"value": "x"}], "color_map": {"x": "accent"}}])
    assert "/layout/1/by  runs 的 color_map 必须配合 by（按哪个槽位取色）" in errs


def test_runs_may_take_color_from_by(make_repo):
    assert _errors(make_repo, layout=[NOTE, {**RUNS, "runs": [{"value": "x"}], "by": "note", "color_map": {"x": "accent"}}]) == []


def test_runs_in_a_grid_item_use_the_item_scope_and_the_index_bind(make_repo):
    item = [{"type": "text", "box": [0, 0, 100, 20], "style": "body",
             "runs": [{"bind": "#"}, {"value": ". "}, {"bind": "."}]}]
    assert _errors(make_repo, slots=_points_slots(), layout=[NOTE, _points_grid(item=item)]) == []


def test_index_bind_in_top_level_runs_is_an_error(make_repo):
    assert "/layout/1/runs/0/bind  # 只能用在 grid 的 item 内" in _errors(
        make_repo, layout=[NOTE, {**RUNS, "runs": [{"bind": "#"}]}])


@pytest.mark.parametrize("text", [
    {"bind": "note", "runs": [{"value": "x"}]},
    {"value": "x", "runs": [{"value": "x"}]},
    {},
])
def test_text_needs_exactly_one_of_bind_value_runs(make_repo, text):
    template = mini_template(layout=[{"type": "text", "box": [0, 0, 10, 10], "style": "body", **text}])
    repo = make_repo({"common.summary-note": template})
    assert any(e.startswith(f"{F}  /layout/0  以下写法必须且只能满足一种") for e in validate_repo(repo).errors)


@pytest.mark.parametrize("run", [{}, {"bind": "note", "value": "x"}, {"value": "x", "size": 13}, {"value": 1}])
def test_run_needs_exactly_one_of_bind_or_value_and_only_known_fields(make_repo, run):
    template = mini_template(layout=[{"type": "text", "box": [0, 0, 10, 10], "style": "body", "runs": [run]}])
    repo = make_repo({"common.summary-note": template})
    assert any(e.startswith(f"{F}  /layout/0/runs/0") for e in validate_repo(repo).errors)


def test_empty_runs_are_rejected(make_repo):
    template = mini_template(layout=[{"type": "text", "box": [0, 0, 10, 10], "style": "body", "runs": []}])
    assert f"{F}  /layout/0/runs  共 0 项，低于下限 1" in validate_repo(make_repo({"common.summary-note": template})).errors


@pytest.mark.parametrize("shadow, expected", [(True, []), (False, []), ("yes", ["/layout/1/shadow  类型应为 boolean"])])
def test_shadow_is_a_boolean_on_shapes(make_repo, shadow, expected):
    shape = {"type": "shape", "box": [0, 100, 10, 10], "fill": "bg", "shadow": shadow}
    assert _errors(make_repo, layout=[NOTE, shape]) == expected


def test_style_shadow_color_must_be_a_color_token(make_repo, root):
    repo = make_repo({"common.summary-note": mini_template()})
    path = repo / "styles" / "default" / "style.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("color: text, alpha", "color: ink, alpha"), encoding="utf-8")
    assert "styles/default/style.yaml  /shadow/color  未知颜色 token ink" in validate_repo(repo).errors


TEXT_COLOR_HINT = "文字颜色只能用 accent / highlight_strong / primary_text / text / on_primary，实际是"


@pytest.mark.parametrize("token", ["accent", "highlight_strong", "primary_text", "text", "on_primary"])
def test_allowed_text_colors_pass(make_repo, token):
    layout = [{**NOTE, "color": token}, {**RUNS, "runs": [{"bind": "extra", "color": token}]}]
    assert _errors(make_repo, slots=_slots(extra={"type": "string"}), layout=layout) == []


@pytest.mark.parametrize("token", ["muted", "line", "surface", "bg", "highlight"])
def test_text_color_outside_the_three_colors_is_an_error(make_repo, token):
    errs = _errors(make_repo, layout=[{**NOTE, "color": token}])
    assert f"/layout/0/color  {TEXT_COLOR_HINT} {token}" in errs


def test_text_color_map_and_run_colors_follow_the_same_rule(make_repo):
    layout = [NOTE, {**LEVEL_TEXT, "color_map": {"高": "highlight_strong", "中": "muted", "低": "line"}},
              {**RUNS, "runs": [{"bind": "extra", "color": "muted"}, {"value": "：", "color": "text"}]}]
    errs = _errors(make_repo, slots=_slots(level=LEVEL, extra={"type": "string"}), layout=layout)
    assert f"/layout/1/color_map/中  {TEXT_COLOR_HINT} muted" in errs
    assert f"/layout/1/color_map/低  {TEXT_COLOR_HINT} line" in errs
    assert f"/layout/2/runs/0/color  {TEXT_COLOR_HINT} muted" in errs
    assert not [e for e in errs if "/color_map/高" in e or "/runs/1/" in e]


def test_bullets_color_follows_the_same_rule(make_repo):
    bullets = {"type": "bullets", "box": [0, 100, 600, 100], "bind": "items", "style": "body", "color": "muted"}
    errs = _errors(make_repo, slots=_slots(items={"type": "array", "items": {"type": "string"}}), layout=[NOTE, bullets])
    assert f"/layout/1/color  {TEXT_COLOR_HINT} muted" in errs


def test_muted_is_still_fine_for_shape_fills_and_fill_maps(make_repo):
    layout = [NOTE, LEVEL_TEXT, {**LEVEL_SHAPE, "fill": "muted", "fill_map": {"高": "muted"}, "line": "muted"}]
    assert _errors(make_repo, slots=_slots(level=LEVEL), layout=layout) == []


def test_unknown_text_color_is_reported_once_as_unknown(make_repo):
    errs = _errors(make_repo, layout=[{**NOTE, "color": "red"}])
    assert [e for e in errs if "/layout/0/color" in e] == ["/layout/0/color  未知颜色 token red"]


@pytest.mark.parametrize("token", ["muted", "surface"])
def test_style_text_styles_must_use_the_three_colors(make_repo, token):
    repo = make_repo({"common.summary-note": mini_template()})
    path = repo / "styles" / "default" / "style.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("footnote:     { size: 8, color: text }",
                                                             f"footnote:     {{ size: 8, color: {token} }}"), encoding="utf-8")
    assert f"styles/default/style.yaml  /text_styles/footnote/color  {TEXT_COLOR_HINT} {token}" in validate_repo(repo).errors


# ---- image 元素 ----

def _image(**extra):
    return {"type": "image", "box": [0, 100, 300, 200], "bind": "photo", "placeholder": "放一张示意图", **extra}


PHOTO = {"photo": {"type": "string"}}


@pytest.mark.parametrize("image", [{}, {"fit": "cover"}, {"fit": "contain"}, {"when": "photo"}])
def test_image_is_valid(make_repo, image):
    assert _errors(make_repo, slots=_slots(**PHOTO), layout=[NOTE, _image(**image)]) == []


def test_image_slot_must_be_rendered_by_some_element(make_repo):
    assert "/slots/properties/photo  槽位没有被 layout 渲染" in _errors(make_repo, slots=_slots(**PHOTO), layout=[NOTE])


def test_image_requires_a_placeholder(make_repo):
    bare = {k: v for k, v in _image().items() if k != "placeholder"}
    assert "/layout/1  缺少必填字段 placeholder" in _errors(make_repo, slots=_slots(**PHOTO), layout=[NOTE, bare])


def test_image_placeholder_cannot_be_empty(make_repo):
    assert "/layout/1/placeholder  长度 0，低于下限 1" in _errors(
        make_repo, slots=_slots(**PHOTO), layout=[NOTE, _image(placeholder="")])


def test_image_rejects_unknown_fit_and_extra_fields(make_repo):
    errs = _errors(make_repo, slots=_slots(**PHOTO), layout=[NOTE, _image(fit="stretch", style="body")])
    assert any("/layout/1/fit  取值 stretch 不在可选范围" in e for e in errs)
    assert "/layout/1  不允许的字段 style" in errs


def test_image_binds_only_string_slots(make_repo):
    slots = _slots(photo={"type": "array", "maxItems": 2, "items": {"type": "string"}})
    assert "/layout/1/bind  image 只能绑定 string 槽位（图片路径），实际是 array" in _errors(
        make_repo, slots=slots, layout=[NOTE, _image()])


def test_image_bind_must_exist(make_repo):
    assert "/layout/1/bind  槽位 photo 不存在" in _errors(make_repo, slots=_slots(), layout=[NOTE, _image()])


def test_image_bind_cannot_duplicate_another_top_level_binding(make_repo):
    assert "/layout/2/bind  槽位 photo 被重复绑定" in _errors(
        make_repo, slots=_slots(**PHOTO), layout=[NOTE, _image(), _image(box=[0, 300, 100, 100])])


def test_image_when_must_point_to_an_existing_slot(make_repo):
    assert "/layout/1/when  槽位 nope 不存在" in _errors(make_repo, slots=_slots(**PHOTO), layout=[NOTE, _image(when="nope")])


def test_image_must_fit_the_body_area(make_repo):
    assert "/layout/1/box  超出 body 区 1216×560" in _errors(
        make_repo, slots=_slots(**PHOTO), layout=[NOTE, _image(box=[1000, 100, 300, 200])])


ITEM_PIC = {"cards": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {"pic": {"type": "string"}}}}}


def _pic_grid(bind="pic"):
    return {"type": "grid", "box": [0, 100, 600, 200], "bind": "cards", "columns": 3, "gap": 10,
            "item": [{"type": "image", "box": [0, 0, "100%", "100%"], "bind": bind, "placeholder": "配图"}]}


def test_image_in_a_grid_item_binds_the_item_scope(make_repo):
    assert _errors(make_repo, slots=_slots(**ITEM_PIC), layout=[NOTE, _pic_grid()]) == []


def test_image_in_a_grid_item_reports_unknown_item_fields(make_repo):
    assert "/layout/1/item/0/bind  槽位 nope 不存在" in _errors(make_repo, slots=_slots(**ITEM_PIC), layout=[NOTE, _pic_grid("nope")])


# ---- 嵌套 grid ----

CARDS = {"type": "array", "maxItems": 4, "items": {"type": "object", "required": ["name"],
                                                    "properties": {"name": {"type": "string"}}}}
ROWS = {"type": "array", "maxItems": 3, "items": {"type": "object", "required": ["label", "cards"],
                                                   "properties": {"label": {"type": "string"}, "cards": CARDS}}}


def _nested(**inner):
    """外层 grid 每行一个领域（固定行高 100），行内是标签和内层 grid；inner 里的键覆盖内层 grid 元素的字段。"""
    inner_grid = {"type": "grid", "box": [110, 0, "100%-110", "100%"], "bind": "cards", "columns": 4, "gap": 8,
                  "item": [{"type": "text", "box": [0, 0, "100%", 20], "bind": "name", "style": "body"},
                           {"type": "text", "box": [0, 30, 20, 20], "bind": "#", "style": "body"}], **inner}
    return {"type": "grid", "box": [0, 100, 1000, 320], "bind": "rows", "columns": 1, "gap": 10, "row_height": 100,
            "item": [{"type": "text", "box": [0, 0, 100, 20], "bind": "label", "style": "body_strong"}, inner_grid]}


def test_nested_grid_is_valid(make_repo):
    assert _errors(make_repo, slots=_slots(rows=ROWS), layout=[NOTE, _nested()]) == []


def test_nested_grid_bind_resolves_in_the_outer_item_scope(make_repo):
    assert "/layout/1/item/1/bind  槽位 nope 不存在" in _errors(
        make_repo, slots=_slots(rows=ROWS), layout=[NOTE, _nested(bind="nope")])


def test_nested_grid_item_binds_resolve_in_the_inner_item_scope(make_repo):
    inner_item = [{"type": "text", "box": [0, 0, 50, 20], "bind": "label", "style": "body"}]  # label 是外层项的字段
    assert "/layout/1/item/1/item/0/bind  槽位 label 不存在" in _errors(
        make_repo, slots=_slots(rows=ROWS), layout=[NOTE, _nested(item=inner_item)])


def test_nested_grid_array_must_declare_max_items(make_repo):
    rows = {**ROWS, "items": {**ROWS["items"], "properties": {
        "label": {"type": "string"}, "cards": {"type": "array", "items": CARDS["items"]}}}}
    assert "/layout/1/item/1/bind  grid 绑定的数组必须声明 maxItems" in _errors(
        make_repo, slots=_slots(rows=rows), layout=[NOTE, _nested()])


def test_nested_grid_must_bind_an_array(make_repo):
    rows = {**ROWS, "items": {**ROWS["items"], "properties": {"label": {"type": "string"}, "cards": {"type": "string"}}}}
    assert "/layout/1/item/1/bind  grid 只能绑定数组槽位，实际是 string" in _errors(
        make_repo, slots=_slots(rows=rows), layout=[NOTE, _nested()])


def test_index_bind_in_the_inner_item_only_binds_text(make_repo):
    inner_item = [{"type": "image", "box": [0, 0, 10, 10], "bind": "#", "placeholder": "图"}]
    assert "/layout/1/item/1/item/0/bind  # 只能绑定给 text，实际是 image" in _errors(
        make_repo, slots=_slots(rows=ROWS), layout=[NOTE, _nested(item=inner_item)])


def test_nested_grid_item_must_fit_the_inner_min_cell(make_repo):
    # 内层最小单元格：宽 ((1000 - 110) - 3 × 8) / 4 = 216.5、高 100；item 内元素宽 300 放不下
    inner_item = [{"type": "text", "box": [0, 0, 300, 20], "bind": "name", "style": "body"}]
    assert "/layout/1/item/1/item/0/box  按 maxItems=4 计算的单元格 216×100 放不下" in _errors(
        make_repo, slots=_slots(rows=ROWS), layout=[NOTE, _nested(item=inner_item)])


def test_nested_grid_box_must_fit_the_outer_min_cell(make_repo):
    # 外层单元格宽 1000、高 row_height 100；内层 grid 的 box 高 150 放不下
    assert "/layout/1/item/1/box  按 maxItems=3 计算的单元格 1000×100 放不下" in _errors(
        make_repo, slots=_slots(rows=ROWS), layout=[NOTE, _nested(box=[110, 0, "100%-110", 150])])


def test_nested_grid_row_height_must_fit_the_inner_box(make_repo):
    inner = {"row_height": 60, "columns": 2, "box": [110, 0, "100%-110", 100]}  # 最多 4 项 → 2 行 × 60 + 间距 8 = 128 > 100
    errs = _errors(make_repo, slots=_slots(rows=ROWS), layout=[NOTE, _nested(**inner)])
    assert any(e.startswith("/layout/1/item/1/row_height  按 maxItems=4 排 2 行，需要 128px") for e in errs)
