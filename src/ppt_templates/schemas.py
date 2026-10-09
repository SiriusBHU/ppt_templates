"""schema/*.schema.json 的加载，以及把 JSON Schema 校验错误格式化为中文消息。"""

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


@cache
def load_schema(root: Path, name: str) -> dict:
    """读取 <root>/schema/<name>.schema.json。"""
    return json.loads((root / "schema" / f"{name}.schema.json").read_text(encoding="utf-8"))


def message(e: ValidationError) -> str:
    v, limit, inst = e.validator, e.validator_value, e.instance
    if v == "maxLength":
        return f"长度 {len(inst)}，超过上限 {limit}"
    if v == "minLength":
        return f"长度 {len(inst)}，低于下限 {limit}"
    if v == "maxItems":
        return f"共 {len(inst)} 项，超过上限 {limit}"
    if v == "minItems":
        return f"共 {len(inst)} 项，低于下限 {limit}"
    if v == "required":
        return "缺少必填字段 " + "、".join(k for k in limit if k not in inst)
    if v == "const":
        return f"必须是 {limit}，实际是 {inst}"
    if v == "enum":
        return f"取值 {inst} 不在可选范围 {limit}"
    if v == "additionalProperties":
        return "不允许的字段 " + "、".join(k for k in inst if k not in e.schema.get("properties", {}))
    if v == "pattern":
        return f"{inst} 不符合格式 {limit}"
    if v == "type":
        return f"类型应为 {limit}"
    if v == "oneOf":
        return "以下写法必须且只能满足一种：" + " / ".join(json.dumps(s, ensure_ascii=False) for s in limit)
    return e.message


def pointer(parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts) or "/"


def errors(schema: dict, instance, prefix=()) -> list[str]:
    """「<JSON Pointer>  <中文消息>」列表，按路径、消息排序；没有错误时返回空列表。"""
    found = [(list(e.absolute_path), message(e)) for e in Draft202012Validator(schema).iter_errors(instance)]
    found.sort(key=lambda f: ([str(p) for p in f[0]], f[1]))
    return [f"{pointer([*prefix, *path])}  {msg}" for path, msg in found]
