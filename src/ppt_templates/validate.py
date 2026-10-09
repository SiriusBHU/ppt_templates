"""仓库级校验（spec 7.1）：taxonomy、风格、每个模板。"""

from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .errors import PptError
from .loader import load_yaml
from .schemas import errors as schema_errors
from .schemas import load_schema
from .taxonomy import Taxonomy, load_taxonomy

LEVEL_TOPICS = {"system", "hardware", "software"}


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
        if not (tdir / "example.yaml").is_file():
            report.errors.append(f"{rel}  缺少 example.yaml")
        if not (tdir / "preview.png").is_file():
            report.warnings.append(f"{rel}  缺少 preview.png（运行 uv run ppt preview {topic}.{name} --write）")
    return report
