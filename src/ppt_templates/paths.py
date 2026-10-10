"""点号路径：在数据里取值（lookup），在 JSON Schema 里找对应的子 schema（slot_at）。"""

INDEX_BIND = "#"  # grid item 内的特殊 bind：当前项的 1 起序号（字符串），不是点号路径


def lookup(scope, path: str):
    """相对 scope 解析点号路径；"." 是 scope 本身；路径不存在（可选槽位未填）返回 None。"""
    if path == ".":
        return scope
    for key in path.split("."):
        if not isinstance(scope, dict) or key not in scope:
            return None
        scope = scope[key]
    return scope


def is_empty(value) -> bool:
    """None、""、[]、{} 算空（`when` 不成立）；0 和 False 不算。"""
    return value is None or (isinstance(value, (str, list, dict)) and not value)


def slot_at(schema: dict, path: str) -> dict | None:
    """点号路径在 object schema 里对应的子 schema；"." 是 schema 本身；不存在返回 None。"""
    if path == ".":
        return schema
    for key in path.split("."):
        if not isinstance(schema, dict):
            return None
        schema = (schema.get("properties") or {}).get(key)
        if schema is None:
            return None
    return schema
