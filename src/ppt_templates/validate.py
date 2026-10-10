"""仓库级校验（spec 7.1）：taxonomy、风格、每个模板、skill 副本。"""

import math
from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .catalog import catalog_is_current
from .components import COMPONENTS
from .errors import PptError
from .geometry import CANVAS_H, CANVAS_W, REF_H, REF_W, grid_cells, resolve_box
from .images import ImageSource
from .loader import load_yaml, template_dirs
from .paths import INDEX_BIND, slot_at
from .schemas import errors as schema_errors
from .schemas import load_schema
from .skill import check_skill
from .slots import bound_errors
from .taxonomy import Taxonomy, load_taxonomy

LEVEL_TOPICS = {"system", "hardware", "software"}
FRAME_SLOTS = ("title", "title_suffix", "takeaway")
TEXT_COLORS = ("accent", "highlight_strong", "primary", "text", "on_primary")  # 文字只用这几种颜色；muted 等只给非文字元素
EPS = 0.5  # 坐标比较容差（px）


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def style_tokens(root: Path) -> tuple[set[str], set[str]]:
    """(颜色 token, 文字样式 token)：取自 style.schema.json 的 required 列表。"""
    props = load_schema(root, "style")["properties"]
    return set(props["colors"]["required"]), set(props["text_styles"]["required"])


def text_color_error(token: str, colors: set[str]) -> str | None:
    """文字颜色 token 不在允许的几种之内时返回错误消息；未知 token 由别处报告，这里返回 None。"""
    if token in colors and token not in TEXT_COLORS:
        return f"文字颜色只能用 {' / '.join(TEXT_COLORS)}，实际是 {token}"
    return None


def check_style_refs(rel: str, style: dict, colors: set[str], texts: set[str]) -> list[str]:
    """风格内部引用的 token 都要存在：文字样式的颜色、阴影的颜色、页框区域的文字样式、装饰的颜色。"""
    errs = []
    shadow_color = style.get("shadow", {}).get("color")
    if shadow_color is not None and shadow_color not in colors:
        errs.append(f"{rel}  /shadow/color  未知颜色 token {shadow_color}")
    for token, ts in style["text_styles"].items():
        if ts["color"] not in colors:
            errs.append(f"{rel}  /text_styles/{token}/color  未知颜色 token {ts['color']}")
        elif problem := text_color_error(ts["color"], colors):
            errs.append(f"{rel}  /text_styles/{token}/color  {problem}")
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


def _obj(schema) -> dict:
    """子 schema 可能是布尔值（true / false），当作没有任何约束的空 schema。"""
    return schema if isinstance(schema, dict) else {}


def _type_error(el: dict, slot: dict) -> str | None:
    """bind 的槽位类型是否符合元素要求（spec 4.3 表格）；符合返回 None。"""
    kind, t = el["type"], slot.get("type")
    if kind == "text":
        return None if t == "string" else f"text 只能绑定 string 槽位，实际是 {t}"
    if kind == "bullets":
        items = _obj(slot.get("items"))
        props = _obj(items.get("properties"))
        if t == "array" and items.get("type") == "string":
            return None
        text_required = "text" in items.get("required", []) and _obj(props.get("text")).get("type") == "string"
        if t == "array" and items.get("type") == "object" and text_required:
            level = _obj(props.get("level"))
            if "level" in props and (level.get("type") != "integer" or level.get("minimum", -1) < 0):
                return "bullets 的 level 必须是 type: integer 且 minimum: 0"
            return None
        return "bullets 只能绑定 string 数组，或含 string 字段 text 的对象数组"
    if kind == "image":
        return None if t == "string" else f"image 只能绑定 string 槽位（图片路径），实际是 {t}"
    if kind == "grid":
        if t != "array":
            return f"grid 只能绑定数组槽位，实际是 {t}"
        return None if "maxItems" in slot else "grid 绑定的数组必须声明 maxItems"
    want = COMPONENTS[el["component"]].schema.get("type")
    return None if t == want else f"组件 {el['component']} 需要 {want} 类型的槽位，实际是 {t}"


def check_layout(f: str, tpl: dict, colors: set[str], texts: set[str]) -> list[str]:
    """spec 7.1 第 5、7 条：槽位都被渲染、bind / when / by 存在且类型匹配、页框槽位规则、只引用风格 token。"""
    errs = []
    slots, standard = tpl["slots"], tpl["frame"] == "standard"
    props = slots.get("properties") or {}

    def err(ptr, msg):
        errs.append(f"{f}  {ptr}  {msg}")

    if standard:
        if "title" not in slots.get("required", []):
            err("/slots/required", "frame: standard 的模板必须把 title 列为必填")
        for name in FRAME_SLOTS:
            if name in props and _obj(props[name]).get("type") != "string":
                err(f"/slots/properties/{name}", "页框槽位必须是 type: string")

    top_paths = set()

    def check_ref(scope, p, el, key):
        """when / by 的点号路径必须指向存在的槽位。"""
        if slot_at(scope, el[key]) is None:
            err(f"{p}/{key}", f"槽位 {el[key]} 不存在")

    def check_text_color(ptr, token):
        problem = text_color_error(token, colors)
        if problem:
            err(ptr, problem)

    def check_maps(scope, p, el):
        """color_map / fill_map / line_map：值是颜色 token，键在取值槽位的 enum 内，shape 的映射必须有 by。"""
        maps = [key for key in ("color_map", "fill_map", "line_map") if key in el]
        for key in maps:
            for k, token in el[key].items():
                if token not in colors:
                    err(f"{p}/{key}/{k}", f"未知颜色 token {token}")
        if ("fill_map" in el or "line_map" in el) and "by" not in el:
            err(f"{p}/by", "fill_map / line_map 必须用 by 指明按哪个槽位取色")
        path = el.get("by", el.get("bind"))
        if "color_map" in el and path is None:
            err(f"{p}/color_map", "color_map 必须配合 bind 或 by，才知道按哪个值取色")
        enum = _obj(slot_at(scope, path)).get("enum") if path is not None else None
        if enum:
            allowed = {str(v) for v in enum}
            for key in maps:
                for k in el[key]:
                    if str(k) not in allowed:
                        err(f"{p}/{key}/{k}", f"键 {k} 不在槽位 {path} 的可选取值 {enum} 内")

    def check_bind(p, el, scope, top):
        """检查 el 的 bind（text 的 run 按 text 处理）：槽位存在、类型匹配，顶层不重复。通过返回槽位 schema，否则返回 None。"""
        path = el["bind"]
        if path == INDEX_BIND:  # grid item 的序号，不对应任何槽位
            if top:
                err(f"{p}/bind", f"{INDEX_BIND} 只能用在 grid 的 item 内")
            elif el["type"] != "text":
                err(f"{p}/bind", f"{INDEX_BIND} 只能绑定给 text，实际是 {el['type']}")
            return None
        slot = slot_at(scope, path)
        if slot is None:
            err(f"{p}/bind", f"槽位 {path} 不存在")
            return None
        if not isinstance(slot, dict):
            err(f"{p}/bind", "槽位必须是对象 schema")
            return None
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
            return None
        return slot

    def walk(elements, scope, ptr, top):
        for i, el in enumerate(elements):
            p = f"{ptr}/{i}"
            for key in ("fill", "line", "color"):
                if key in el and el[key] not in colors:
                    err(f"{p}/{key}", f"未知颜色 token {el[key]}")
            if "style" in el and el["style"] not in texts:
                err(f"{p}/style", f"未知文字样式 token {el['style']}")
            for key in ("when", "by"):
                if key in el:
                    check_ref(scope, p, el, key)
            check_maps(scope, p, el)
            if el["type"] in ("text", "bullets"):
                if "color" in el:
                    check_text_color(f"{p}/color", el["color"])
                for k, token in el.get("color_map", {}).items():
                    check_text_color(f"{p}/color_map/{k}", token)
            if "runs" in el:
                for key in ("color_map", "by"):
                    if key in el:
                        err(f"{p}/{key}", f"runs 不支持 {key}，请在 run 上写 color")
                for k, run in enumerate(el["runs"]):
                    rp = f"{p}/runs/{k}"
                    if "color" in run and run["color"] not in colors:
                        err(f"{rp}/color", f"未知颜色 token {run['color']}")
                    elif "color" in run:
                        check_text_color(f"{rp}/color", run["color"])
                    if "style" in run and run["style"] not in texts:
                        err(f"{rp}/style", f"未知文字样式 token {run['style']}")
                    if "bind" in run:
                        check_bind(rp, {"type": "text", "bind": run["bind"]}, scope, top)
            if el["type"] == "component":
                if el["component"] not in COMPONENTS:
                    err(f"{p}/component", f"未知组件 {el['component']}")
                    continue
                prefix = (*p[1:].split("/"), "props")
                errs.extend(f"{f}  {e}（组件 {el['component']}）" for e in
                            schema_errors(COMPONENTS[el["component"]].props_schema, el.get("props", {}), prefix=prefix))
            if "bind" not in el:
                continue
            slot = check_bind(p, el, scope, top)
            if slot is not None and el["type"] == "grid":
                walk(el["item"], _obj(slot.get("items")), f"{p}/item", False)

    walk(tpl["layout"], slots, "/layout", True)
    rendered = {path.split(".")[0] for path in top_paths}
    for name in props:
        if not (standard and name in FRAME_SLOTS) and name not in rendered:
            err(f"/slots/properties/{name}", "槽位没有被 layout 渲染")
    return errs


def _fits(box, w: float, h: float) -> bool:
    x, y, bw, bh = box
    return bw >= 0 and bh >= 0 and x >= -EPS and y >= -EPS and x + bw <= w + EPS and y + bh <= h + EPS


def check_geometry(f: str, tpl: dict) -> list[str]:
    """spec 7.1 第 6 条：元素落在绘制区域内；grid 的 item 按 maxItems 算出的最小单元格放得下，嵌套的 grid 逐层往下查。"""
    errs = []
    standard = tpl["frame"] == "standard"
    w, h = (REF_W, REF_H) if standard else (CANVAS_W, CANVAS_H)
    area = "body 区" if standard else "画布"

    def walk(elements, scope, ptr, w, h, outside):
        """scope = 当前作用域的 schema；(w, h) = 父区域尺寸；outside = 元素超出父区域时的说明。"""
        for i, el in enumerate(elements):
            p = f"{ptr}/{i}"
            box = resolve_box(el["box"], w, h)
            if not _fits(box, w, h):
                errs.append(f"{f}  {p}/box  {outside}")
            if el["type"] != "grid":
                continue
            slot = _obj(slot_at(scope, el["bind"]))
            n = slot.get("maxItems")
            if not n:
                continue  # 缺 maxItems 已由 check_layout 报告
            gap, row_height = el.get("gap", 0), el.get("row_height")
            cw, ch = grid_cells(box, el["columns"], gap, n, row_height)[0][2:]  # 项数越多单元格越小：maxItems 是最坏情况
            if cw <= 0 or ch <= 0:
                errs.append(f"{f}  {p}/box  按 maxItems={n} 计算的单元格 {cw:.0f}×{ch:.0f} 不是正数（gap 过大或 box 过小）")
                continue
            if row_height is not None:
                rows = math.ceil(n / min(el["columns"], n))
                need = rows * row_height + gap * (rows - 1)
                if need > box[3] + EPS:
                    errs.append(f"{f}  {p}/row_height  按 maxItems={n} 排 {rows} 行，需要 {need:g}px"
                                f"（{rows}×{row_height:g} + 间距 {gap * (rows - 1):g}），超过 box 高 {box[3]:g}px")
            walk(el["item"], _obj(slot.get("items")), f"{p}/item", cw, ch, f"按 maxItems={n} 计算的单元格 {cw:.0f}×{ch:.0f} 放不下")

    walk(tpl["layout"], tpl["slots"], "/layout", w, h, f"超出 {area} {w}×{h}")
    return errs


def check_example(rel: str, tpl: dict, example, images: ImageSource) -> list[str]:
    """spec 7.1 第 8 条：example 通过 slots；绑定到组件的数据还要通过组件自己的 schema 和语义检查；image 的路径要能找到图片。"""
    f = f"{rel}/example.yaml"
    problems = schema_errors(tpl["slots"], example) or bound_errors(tpl, example, images)
    return [f"{f}  {e}" for e in problems]


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
    for tdir in template_dirs(root):
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
            report.errors += check_example(rel, tpl, load_yaml(tdir / "example.yaml"), ImageSource(tdir))
        else:
            report.errors.append(f"{rel}  缺少 example.yaml")
        if not (tdir / "preview.png").is_file():
            report.warnings.append(f"{rel}  缺少 preview.png（运行 uv run ppt preview {topic}.{name} --write）")
    report.errors += check_skill(root)
    if not report.errors and not catalog_is_current(root):
        report.errors.append("catalog.json 不是最新的（运行 uv run ppt catalog）")
    return report
