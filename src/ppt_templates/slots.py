"""用模板的 slots（JSON Schema）校验页内容，并补全 default。"""

from copy import deepcopy
from pathlib import Path

from .errors import PptError
from .loader import load_template
from .schemas import errors, load_schema


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


def prepare_pages(deck, root: Path) -> list[tuple[dict, dict]]:
    """校验 deck 结构和每页内容，返回 [(template, 补全默认值后的 data)]；有错则汇总后抛 PptError。"""
    structure = errors(load_schema(root, "deck"), deck)
    if structure:
        raise PptError("deck 结构错误：\n" + "\n".join(structure))
    pages, problems = [], []
    for i, page in enumerate(deck["pages"]):
        tid = page["template"]
        where = f"第 {i + 1} 页 {tid}"
        try:
            template = load_template(root, tid)
        except PptError as e:
            problems.append(f"{where}  /pages/{i}/template  {e}")
            continue
        found = errors(template["slots"], page["data"], prefix=("pages", i, "data"))
        problems += [f"{where}  {e}" for e in found]
        if not found:
            pages.append((template, fill_defaults(template["slots"], page["data"])))
    if problems:
        raise PptError("\n".join(problems))
    return pages
