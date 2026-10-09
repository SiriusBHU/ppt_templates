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
