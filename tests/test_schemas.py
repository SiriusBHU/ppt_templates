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
    ok = {"style": "default", "pages": [{"template": "system.solution-layered-arch", "data": {}}]}
    assert errors(schema, ok) == []
    assert errors(schema, {"pages": []}) == ["/pages  共 0 项，低于下限 1"]
    assert errors(schema, {"pages": [{"template": "x", "data": {}, "extra": 1}]}) == [
        "/pages/0  不允许的字段 extra",
        "/pages/0/template  x 不符合格式 ^[a-z]+\\.[a-z0-9]+(-[a-z0-9]+)*$",
    ]
