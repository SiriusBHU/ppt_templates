"""仓库级校验（spec 7.1）：taxonomy、风格、每个模板。"""

import math
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .components import COMPONENTS
from .errors import PptError
from .geometry import CANVAS_H, CANVAS_W, REF_H, REF_W, resolve_box
from .loader import load_yaml
from .paths import lookup, slot_at
from .schemas import errors as schema_errors
from .schemas import load_schema
from .taxonomy import Taxonomy, load_taxonomy

LEVEL_TOPICS = {"system", "hardware", "software"}
FRAME_SLOTS = ("title", "title_suffix", "takeaway")
EPS = 0.5  # 坐标比较容差（px）


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def style_tokens(root: Path) -> tuple[set[str], set[str]]:
    """(颜色 token, 文字样式 token)：取自 style.schema.json 的 required 列表。"""
    props = load_schema(root, "style")["properties"]
    return set(props["colors"]["required"]), set(props["text_styles"]["required"])


def check_style_refs(rel: str, style: dict, colors: set[str], texts: set[str]) -> list[str]:
    """风格内部引用的 token 都要存在：文字样式的颜色、页框区域的文字样式、装饰的颜色。"""
    errs = []
    for token, ts in style["text_styles"].items():
        if ts["color"] not in colors:
            errs.append(f"{rel}  /text_styles/{token}/color  未知颜色 token {ts['color']}")
    for region in ("title", "takeaway"):
        for key in ("style", "suffix_style"):
            value = style["frame"][region].get(key)
            if value is not None and value not in texts:
                errs.append(f"{rel}  /frame/{region}/{key}  未知文字样式 token {value}")
    for i, deco in enumerate(style["frame"].get("decorations", [])):
        for key in ("fill", "line"):
            if key in deco and deco[key] not in colors:
                errs.append(f"{rel}  /frame/decorations/{i}/{key}  未知颜色 token {deco[key]}")
    return errs


def check_meta(f: str, topic: str, name: str, tpl: dict, tax: Taxonomy) -> list[str]:
    """spec 7.1 第 3 条：id 与路径、主题、页功能、目录名前缀、-read 后缀、also_fits、level。"""
    errs = []

    def err(ptr, msg):
        errs.append(f"{f}  {ptr}  {msg}")

    if tpl["id"] != f"{topic}.{name}":
        err("/id", f"应为 {topic}.{name}（由目录决定），实际是 {tpl['id']}")
    if topic not in tax.topics:
        err("/", f"主题目录 {topic} 不在 taxonomy.yaml 中")
    for i, role in enumerate(tpl["roles"]):
        if role not in tax.roles:
            err(f"/roles/{i}", f"页功能 {role} 不在 taxonomy.yaml 中")
    if not name.startswith(tpl["roles"][0] + "-"):
        err("/roles/0", f"目录名 {name} 必须以主页功能 {tpl['roles'][0]}- 开头")
    if name.endswith("-read") != (tpl.get("density", "talk") == "read"):
        err("/density", "目录名以 -read 结尾，当且仅当 density: read")
    for i, other in enumerate(tpl.get("also_fits", [])):
        if other not in tax.topics:
            err(f"/also_fits/{i}", f"主题 {other} 不在 taxonomy.yaml 中")
        elif other == topic:
            err(f"/also_fits/{i}", "不能包含模板自己的主题")
    if "level" in tpl and topic not in LEVEL_TOPICS:
        err("/level", f"level 只用于 {'、'.join(sorted(LEVEL_TOPICS))} 主题")
    return errs


def _type_error(el: dict, slot: dict) -> str | None:
    """bind 的槽位类型是否符合元素要求（spec 4.3 表格）；符合返回 None。"""
    kind, t = el["type"], slot.get("type")
    if kind == "text":
        return None if t == "string" else f"text 只能绑定 string 槽位，实际是 {t}"
    if kind == "bullets":
        items = slot.get("items") or {}
        text_ok = (items.get("properties") or {}).get("text", {}).get("type") == "string"
        if t == "array" and (items.get("type") == "string" or (items.get("type") == "object" and text_ok)):
            return None
        return "bullets 只能绑定 string 数组，或含 string 字段 text 的对象数组"
    if kind == "grid":
        if t != "array":
            return f"grid 只能绑定数组槽位，实际是 {t}"
        return None if "maxItems" in slot else "grid 绑定的数组必须声明 maxItems"
    want = COMPONENTS[el["component"]].schema.get("type")
    return None if t == want else f"组件 {el['component']} 需要 {want} 类型的槽位，实际是 {t}"


def check_layout(f: str, tpl: dict, colors: set[str], texts: set[str]) -> list[str]:
    """spec 7.1 第 5、7 条：槽位都被渲染、bind 存在且类型匹配、页框槽位规则、只引用风格 token。"""
    errs = []
    slots, standard = tpl["slots"], tpl["frame"] == "standard"
    props = slots.get("properties") or {}

    def err(ptr, msg):
        errs.append(f"{f}  {ptr}  {msg}")

    if standard:
        if "title" not in slots.get("required", []):
            err("/slots/required", "frame: standard 的模板必须把 title 列为必填")
        for name in FRAME_SLOTS:
            if name in props and props[name].get("type") != "string":
                err(f"/slots/properties/{name}", "页框槽位必须是 type: string")

    top_paths = set()

    def walk(elements, scope, ptr, top):
        for i, el in enumerate(elements):
            p = f"{ptr}/{i}"
            for key in ("fill", "line", "color"):
                if key in el and el[key] not in colors:
                    err(f"{p}/{key}", f"未知颜色 token {el[key]}")
            if "style" in el and el["style"] not in texts:
                err(f"{p}/style", f"未知文字样式 token {el['style']}")
            if el["type"] == "component" and el["component"] not in COMPONENTS:
                err(f"{p}/component", f"未知组件 {el['component']}")
                continue
            if "bind" not in el:
                continue
            path = el["bind"]
            slot = slot_at(scope, path)
            if slot is None:
                err(f"{p}/bind", f"槽位 {path} 不存在")
                continue
            if top:
                head = path.split(".")[0]
                if path in top_paths:
                    err(f"{p}/bind", f"槽位 {path} 被重复绑定")
                top_paths.add(path)
                if standard and head in FRAME_SLOTS:
                    err(f"{p}/bind", f"{head} 由页框渲染，layout 不能再绑定")
            problem = _type_error(el, slot)
            if problem:
                err(f"{p}/bind", problem)
            elif el["type"] == "grid":
                walk(el["item"], slot.get("items") or {}, f"{p}/item", False)

    walk(tpl["layout"], slots, "/layout", True)
    rendered = {path.split(".")[0] for path in top_paths}
    for name in props:
        if not (standard and name in FRAME_SLOTS) and name not in rendered:
            err(f"/slots/properties/{name}", "槽位没有被 layout 渲染")
    return errs


def _fits(box, w: float, h: float) -> bool:
    x, y, bw, bh = box
    return x >= -EPS and y >= -EPS and x + bw <= w + EPS and y + bh <= h + EPS


def check_geometry(f: str, tpl: dict) -> list[str]:
    """spec 7.1 第 6 条：元素落在绘制区域内；grid 的 item 按 maxItems 算出的最小单元格放得下。"""
    errs = []
    standard = tpl["frame"] == "standard"
    w, h = (REF_W, REF_H) if standard else (CANVAS_W, CANVAS_H)
    area = "body 区" if standard else "画布"
    for i, el in enumerate(tpl["layout"]):
        box = resolve_box(el["box"], w, h)
        if not _fits(box, w, h):
            errs.append(f"{f}  /layout/{i}/box  超出 {area} {w}×{h}")
        if el["type"] != "grid":
            continue
        n = (slot_at(tpl["slots"], el["bind"]) or {}).get("maxItems")
        if not n:
            continue  # 缺 maxItems 已由 check_layout 报告
        cols, gap = el["columns"], el.get("gap", 0)
        rows = math.ceil(n / cols)
        cw = (box[2] - gap * (cols - 1)) / cols
        ch = (box[3] - gap * (rows - 1)) / rows
        for j, sub in enumerate(el["item"]):
            if not _fits(resolve_box(sub["box"], cw, ch), cw, ch):
                errs.append(f"{f}  /layout/{i}/item/{j}/box  按 maxItems={n} 计算的单元格 {cw:.0f}×{ch:.0f} 放不下")
    return errs


def check_example(rel: str, tpl: dict, example) -> list[str]:
    """spec 7.1 第 8 条：example 通过 slots；绑定到组件的数据还要通过组件自己的 schema。"""
    f = f"{rel}/example.yaml"
    problems = [f"{f}  {e}" for e in schema_errors(tpl["slots"], example)]
    if problems:
        return problems

    def walk(elements, scope, prefix):
        for el in elements:
            if "bind" not in el:
                continue
            value = lookup(scope, el["bind"])
            here = prefix if el["bind"] == "." else (*prefix, *el["bind"].split("."))
            if el["type"] == "component" and el["component"] in COMPONENTS and value is not None:
                problems.extend(f"{f}  {e}（组件 {el['component']}）"
                                for e in schema_errors(COMPONENTS[el["component"]].schema, value, prefix=here))
            elif el["type"] == "grid" and isinstance(value, list):
                for j, item in enumerate(value):
                    walk(el["item"], item, (*here, j))

    walk(tpl["layout"], example, ())
    return problems


def _template_dirs(root: Path) -> list[Path]:
    return sorted(p for p in (root / "templates").glob("*/*") if p.is_dir() and not p.name.startswith("."))


def validate_repo(root: Path) -> Report:
    report = Report()
    try:
        tax = load_taxonomy(root)
    except PptError as e:
        report.errors += str(e).splitlines()
        return report

    colors, texts = style_tokens(root)
    style_schema = load_schema(root, "style")
    for sdir in sorted(p for p in (root / "styles").iterdir() if p.is_dir()):
        rel = f"styles/{sdir.name}/style.yaml"
        style = load_yaml(sdir / "style.yaml")
        problems = [f"{rel}  {e}" for e in schema_errors(style_schema, style)]
        report.errors += problems or check_style_refs(rel, style, colors, texts)

    template_schema = load_schema(root, "template")
    for tdir in _template_dirs(root):
        topic, name = tdir.parent.name, tdir.name
        rel = f"templates/{topic}/{name}"
        f = f"{rel}/template.yaml"
        if not (tdir / "template.yaml").is_file():
            report.errors.append(f"{rel}  缺少 template.yaml")
            continue
        tpl = load_yaml(tdir / "template.yaml")
        problems = [f"{f}  {e}" for e in schema_errors(template_schema, tpl)]
        if not problems:
            try:
                Draft202012Validator.check_schema(tpl["slots"])
            except SchemaError as e:
                problems.append(f"{f}  /slots  不是合法的 JSON Schema：{e.message}")
        if not problems and tpl["slots"].get("type") != "object":
            problems.append(f"{f}  /slots/type  顶层必须是 type: object")
        if problems:
            report.errors += problems
            continue
        report.errors += check_meta(f, topic, name, tpl, tax)
        report.errors += check_layout(f, tpl, colors, texts)
        report.errors += check_geometry(f, tpl)
        if (tdir / "example.yaml").is_file():
            report.errors += check_example(rel, tpl, load_yaml(tdir / "example.yaml"))
        else:
            report.errors.append(f"{rel}  缺少 example.yaml")
        if not (tdir / "preview.png").is_file():
            report.warnings.append(f"{rel}  缺少 preview.png（运行 uv run ppt preview {topic}.{name} --write）")
    return report
