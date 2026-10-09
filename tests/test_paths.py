from ppt_templates.paths import lookup, slot_at


def test_slot_at():
    schema = {"type": "object", "properties": {"a": {"type": "object", "properties": {"b": {"type": "string"}}}}}
    assert slot_at(schema, "a.b") == {"type": "string"}
    assert slot_at(schema, ".") is schema
    assert slot_at(schema, "a.c") is None
    assert slot_at(schema, "x.y") is None


def test_lookup():
    assert lookup({"a": {"b": "x"}}, "a.b") == "x"
    assert lookup({"a": {}}, "a.b") is None
    assert lookup("item", ".") == "item"
