"""读取仓库里的 style / template / deck YAML。"""

from pathlib import Path

import yaml

from .errors import PptError


def find_repo_root(start: Path | None = None) -> Path:
    """最近的、含 taxonomy.yaml 的祖先目录；先从 start（默认当前目录）找，找不到再从包所在位置找。"""
    for origin in (start or Path.cwd(), Path(__file__)):
        for d in (origin.resolve(), *origin.resolve().parents):
            if (d / "taxonomy.yaml").is_file():
                return d
    raise PptError("找不到仓库根目录（含 taxonomy.yaml 的祖先目录）")


def load_yaml(path: Path):
    if not path.is_file():
        raise PptError(f"文件不存在: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


FONT = "微软雅黑"
# 所有模板、所有风格统一的字号（pt）：风格只能改颜色等，不能改字号
TEXT_SIZES = {
    "title": 24, "title_suffix": 18, "subtitle": 18, "emphasis": 14, "body": 12, "body_strong": 12,
    "detail": 10, "caption": 9, "footnote": 8, "kpi": 24,
}


def load_style(root: Path, name: str) -> dict:
    """读取风格并检查硬性约束：字体统一为微软雅黑，文字样式集合与字号与 TEXT_SIZES 完全一致。"""
    style = load_yaml(root / "styles" / name / "style.yaml")
    if any(style["fonts"].get(k) != FONT for k in ("cjk", "latin")):
        raise PptError(f"风格 {name}: fonts.cjk / fonts.latin 必须都是{FONT}")
    if set(style["text_styles"]) != set(TEXT_SIZES):
        raise PptError(f"风格 {name}: 文字样式必须正好是 {sorted(TEXT_SIZES)}")
    for token, ts in style["text_styles"].items():
        if ts["size"] != TEXT_SIZES[token]:
            raise PptError(f"风格 {name}: 文字样式 {token} 的字号必须是 {TEXT_SIZES[token]}，实际是 {ts['size']}")
    return style


def template_dir(root: Path, template_id: str) -> Path:
    topic, _, name = str(template_id).partition(".")
    if not topic or not name:
        raise PptError(f"模板 id 应为 <主题>.<名称>: {template_id}")
    return root / "templates" / topic / name


def load_template(root: Path, template_id: str) -> dict:
    path = template_dir(root, template_id) / "template.yaml"
    if not path.is_file():
        raise PptError("模板不存在")
    return load_yaml(path)


def load_example(root: Path, template_id: str) -> dict:
    return load_yaml(template_dir(root, template_id) / "example.yaml")


def load_deck(path: Path) -> dict:
    return load_yaml(path)
