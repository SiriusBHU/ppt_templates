"""用模板的 slots（JSON Schema）校验页内容，并补全 default。"""

from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .errors import PptError
from .loader import load_template


def fill_defaults(schema: dict, value):
    """返回补全了缺失字段 default 的副本，递归处理 object 和 array。"""
    if isinstance(value, dict):
        out = {}
        for key, sub in schema.get("properties", {}).items():
            if key not in value and "default" in sub:
                out[key] = deepcopy(sub["default"])
        for key, item in value.items():
            sub = schema.get("properties", {}).get(key)
            out[key] = fill_defaults(sub, item) if sub else deepcopy(item)
        return out
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return [fill_defaults(schema["items"], item) for item in value]
    return deepcopy(value)


def _message(e: ValidationError) -> str:
    v, limit = e.validator, e.validator_value
    if v == "maxLength":
        return f"长度 {len(e.instance)}，超过上限 {limit}"
    if v == "minLength":
        return f"长度 {len(e.instance)}，低于下限 {limit}"
    if v == "maxItems":
        return f"共 {len(e.instance)} 项，超过上限 {limit}"
    if v == "minItems":
        return f"共 {len(e.instance)} 项，低于下限 {limit}"
    if v == "required":
        return "缺少必填字段 " + "、".join(k for k in limit if k not in e.instance)
    return e.message


def _pointer(parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts)


def prepare_pages(deck: dict, root: Path) -> list[tuple[dict, dict]]:
    """校验 deck 的每一页，返回 [(template, 补全默认值后的 data)]；有错则汇总后抛 PptError。"""
    pages, errors = [], []
    for i, page in enumerate(deck.get("pages") or []):
        tid = page.get("template")
        where = f"第 {i + 1} 页 {tid}"
        try:
            template = load_template(root, tid)
        except PptError as e:
            errors.append(f"{where}  /pages/{i}/template  {e}")
            continue
        data = page.get("data") or {}
        found = sorted(
            Draft202012Validator(template["slots"]).iter_errors(data),
            key=lambda e: [str(p) for p in e.absolute_path],
        )
        errors += [f"{where}  {_pointer(['pages', i, 'data', *e.absolute_path])}  {_message(e)}" for e in found]
        if not found:
            pages.append((template, fill_defaults(template["slots"], data)))
    if errors:
        raise PptError("\n".join(errors))
    return pages
