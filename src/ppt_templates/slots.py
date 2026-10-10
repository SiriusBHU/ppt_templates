"""用模板的 slots（JSON Schema）和绑定的组件校验页内容，并补全 default。"""

from copy import deepcopy
from pathlib import Path

from .components import COMPONENTS
from .errors import PptError
from .geometry import CANVAS_H, CANVAS_W, REF_H, REF_W, grid_cells, resolve_box
from .images import ImageSource
from .loader import load_template
from .paths import INDEX_BIND, is_empty, lookup
from .schemas import errors, load_schema, pointer


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


def bound_errors(template: dict, data, images: ImageSource, prefix=()) -> list[str]:
    """layout 里绑定的值再查一遍 slots 管不到的部分：组件的数据要通过组件的 schema 和语义检查，返回「<JSON Pointer>  <消息>（组件 <名>）」；
    image 的路径要能解析到图片，返回「<JSON Pointer>  <消息>」。data 须已通过 template 的 slots；prefix 是 data 在整份文档里的路径。"""
    problems = []

    def walk(elements, scope, here, area):
        for el in elements:
            if "bind" not in el or el["bind"] == INDEX_BIND or ("when" in el and is_empty(lookup(scope, el["when"]))):
                continue  # 不渲染的元素不检查它的数据
            value = lookup(scope, el["bind"])
            at = here if el["bind"] == "." else (*here, *el["bind"].split("."))
            box = resolve_box(el["box"], *area)
            if el["type"] == "component" and el["component"] in COMPONENTS and value is not None:
                comp = COMPONENTS[el["component"]]
                found = errors(comp.schema, value, prefix=at) or [
                    f"{pointer([*at, *path])}  {msg}" for path, msg in comp.check(value, box)]
                problems.extend(f"{e}（组件 {el['component']}）" for e in found)
            elif el["type"] == "image" and not is_empty(value):
                try:
                    images.resolve(value)
                except PptError as e:
                    problems.append(f"{pointer(at)}  {e}")
            elif el["type"] == "grid" and isinstance(value, list):
                cells = grid_cells(box, el["columns"], el.get("gap", 0), len(value), el.get("row_height"))
                for j, (item, cell) in enumerate(zip(value, cells)):
                    walk(el["item"], item, (*at, j), cell[2:])

    standard = template.get("frame", "standard") == "standard"
    walk(template["layout"], data, tuple(prefix), (REF_W, REF_H) if standard else (CANVAS_W, CANVAS_H))
    return problems


def prepare_pages(deck, root: Path, images: ImageSource | None = None) -> list[tuple[dict, dict]]:
    """校验 deck 结构和每页内容，返回 [(template, 补全默认值后的 data)]；有错则汇总后抛 PptError。
    images 决定 image 元素的路径怎么解析；省略则相对当前目录、不限制。"""
    images = images or ImageSource(Path.cwd())
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
        found = found or bound_errors(template, page["data"], images, ("pages", i, "data"))
        problems += [f"{where}  {e}" for e in found]
        if not found:
            pages.append((template, fill_defaults(template["slots"], page["data"])))
    if problems:
        raise PptError("\n".join(problems))
    return pages
