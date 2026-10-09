"""读取仓库里的 style / template / deck YAML。"""

import re
from pathlib import Path

import yaml

from .errors import PptError
from .schemas import errors, load_schema


def find_repo_root(start: Path | None = None) -> Path:
    """最近的、含 taxonomy.yaml 的祖先目录；先从 start（默认当前目录）找，找不到再从包所在位置找。"""
    for origin in (start or Path.cwd(), Path(__file__)):
        for d in (origin.resolve(), *origin.resolve().parents):
            if (d / "taxonomy.yaml").is_file():
                return d
    raise PptError("找不到仓库根目录（含 taxonomy.yaml 的祖先目录）")


_BOOL_TAG = "tag:yaml.org,2002:bool"


class _Yaml12Loader(yaml.SafeLoader):
    """布尔值按 YAML 1.2：只有 true / false（大小写三种写法）是布尔；no / yes / on / off 保持字符串。"""


_Yaml12Loader.yaml_implicit_resolvers = {
    first: [(tag, pattern) for tag, pattern in resolvers if tag != _BOOL_TAG]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12Loader.add_implicit_resolver(_BOOL_TAG, re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF"))


def load_yaml(path: Path):
    if not path.is_file():
        raise PptError(f"文件不存在: {path}")
    try:
        return yaml.load(path.read_text(encoding="utf-8"), Loader=_Yaml12Loader)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f"第 {mark.line + 1} 行第 {mark.column + 1} 列：" if mark else ""
        raise PptError(f"{path}  /  YAML 语法错误：{where}{getattr(e, 'problem', None) or e}") from e


FONT = "微软雅黑"


def load_style(root: Path, name: str) -> dict:
    """读取风格，并按 schema/style.schema.json 检查：字体固定微软雅黑，文字样式与字号固定。"""
    style = load_yaml(root / "styles" / name / "style.yaml")
    problems = errors(load_schema(root, "style"), style)
    if problems:
        raise PptError(f"风格 {name} 不合规：\n" + "\n".join(problems))
    return style


def template_dirs(root: Path) -> list[Path]:
    """templates/<主题>/<模板名>/ 目录，排序；跳过任何以 . 开头的目录。"""
    return sorted(p for p in (root / "templates").glob("*/*")
                  if p.is_dir() and not p.name.startswith(".") and not p.parent.name.startswith("."))


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
