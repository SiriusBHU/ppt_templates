from ppt_templates.schemas import errors, load_schema


def test_errors_are_sorted_pointer_prefixed_and_chinese():
    schema = {
        "type": "object",
        "required": ["a"],
        "additionalProperties": False,
        "properties": {
            "b": {"type": "string", "maxLength": 2},
            "c": {"const": 12},
            "d": {"enum": ["x", "y"]},
        },
    }
    assert errors(schema, {"b": "长长长", "c": 13, "d": "z", "e": 1}, prefix=("pages", 0)) == [
        "/pages/0  不允许的字段 e",
        "/pages/0  缺少必填字段 a",
        "/pages/0/b  长度 3，超过上限 2",
        "/pages/0/c  必须是 12，实际是 13",
        "/pages/0/d  取值 z 不在可选范围 ['x', 'y']",
    ]


def test_root_pointer_is_slash():
    assert errors({"type": "object", "required": ["a"]}, {}) == ["/  缺少必填字段 a"]


def test_deck_schema(root):
    schema = load_schema(root, "deck")
    ok = {"style": "default", "pages": [{"template": "system.solution-arch-overview", "data": {}}]}
    assert errors(schema, ok) == []
    assert errors(schema, {"pages": []}) == ["/pages  共 0 项，低于下限 1"]
    assert errors(schema, {"style": "../x", "pages": [ok["pages"][0]]}) == ["/style  ../x 不符合格式 ^[a-z0-9]+(-[a-z0-9]+)*$"]
    assert errors(schema, {"pages": [{"template": "x", "data": {}, "extra": 1}]}) == [
        "/pages/0  不允许的字段 extra",
        "/pages/0/template  x 不符合格式 ^[a-z]+\\.[a-z0-9]+(-[a-z0-9]+)*$",
    ]


def test_array_indexes_sort_numerically():
    schema = {"type": "array", "items": {"type": "string"}}
    found = errors(schema, [*(["x"] * 2), 1, *(["x"] * 7), 2])
    assert found == ["/2  类型应为 string", "/10  类型应为 string"]


def test_every_constraint_message_is_chinese():
    cases = [
        ({"minimum": 3}, 2, "取值 2，低于下限 3"),
        ({"maximum": 3}, 4, "取值 4，超过上限 3"),
        ({"exclusiveMinimum": 0}, 0, "取值 0，必须大于 0"),
        ({"exclusiveMaximum": 5}, 5, "取值 5，必须小于 5"),
        ({"multipleOf": 5}, 7, "取值 7 必须是 5 的整数倍"),
        ({"uniqueItems": True}, [1, 1], "数组中有重复项"),
        ({"minProperties": 2}, {"a": 1}, "共 1 个字段，低于下限 2"),
        ({"maxProperties": 1}, {"a": 1, "b": 2}, "共 2 个字段，超过上限 1"),
        ({"anyOf": [{"type": "string"}, {"type": "integer"}]}, 1.5,
         '必须至少满足以下写法之一：{"type": "string"} / {"type": "integer"}'),
        ({"not": {"type": "string"}}, "x", '不能是 {"type": "string"} 这种写法'),
        ({"contains": {"const": 1}}, [2], "不满足约束 contains"),
        ({"dependentRequired": {"a": ["b"]}}, {"a": 1}, "不满足约束 dependentRequired"),
    ]
    for constraint, instance, expected in cases:
        assert errors(constraint, instance) == [f"/  {expected}"], constraint


def test_false_subschema_message_is_chinese():
    assert errors(False, 1) == ["/  不允许出现该值"]
