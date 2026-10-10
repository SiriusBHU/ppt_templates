"""Agent skill：正本在 .agents/skills，各家工具读的副本由 ppt sync-skill 复制，ppt validate 检查两者一致。"""

import shutil
from pathlib import Path

import yaml

from .errors import PptError

SKILLS = ("ppt-templates", "pptx-to-template")
DESCRIPTION_MAX = 1024


def source_path(name: str) -> Path:
    return Path(".agents/skills") / name / "SKILL.md"


def copy_path(name: str) -> Path:
    """Claude Code 只读 .claude/skills，对软链的发现不稳定，所以放真实副本。"""
    return Path(".claude/skills") / name / "SKILL.md"


def sync_skill(root: Path) -> list[Path]:
    """把每个 skill 的正本复制到副本位置，返回写入的路径。"""
    for name in SKILLS:
        if not (root / source_path(name)).is_file():
            raise PptError(f"{source_path(name)}  /  正本不存在")
    written = []
    for name in SKILLS:
        target = root / copy_path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / source_path(name), target)
        written.append(target)
    return written


def _frontmatter_errors(name: str, text: str) -> list[str]:
    """正本的 frontmatter：name 与目录名一致，description 非空且不超过 1024 字。"""
    source = source_path(name)
    text = text.replace("\r\n", "\n")  # Windows 上编辑或检出的文件可能是 CRLF
    parts = text.split("---\n", 2) if text.startswith("---\n") else []
    if len(parts) < 3:
        return [f"{source}  /  缺少 frontmatter（文件开头应为 --- 包起来的 YAML）"]
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return [f"{source}  /  frontmatter 不是合法的 YAML：{e}"]
    if not isinstance(meta, dict):
        return [f"{source}  /  frontmatter 必须是键值对"]
    errs = []
    if meta.get("name") != name:
        errs.append(f"{source}  /name  必须与目录名 {name} 一致，实际是 {meta.get('name')!r}")
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        errs.append(f"{source}  /description  不能为空")
    elif len(description) > DESCRIPTION_MAX:
        errs.append(f"{source}  /description  长度 {len(description)}，超过上限 {DESCRIPTION_MAX}")
    return errs


def check_skill(root: Path) -> list[str]:
    """仓库里有 .agents/skills 才检查：每个 skill 的正本存在且 frontmatter 合法，副本与正本逐字节一致。"""
    if not (root / ".agents" / "skills").is_dir():
        return []
    errs = []
    for name in SKILLS:
        source, copy = source_path(name), copy_path(name)
        if not (root / source).is_file():
            errs.append(f"{source}  /  正本不存在")
            continue
        content = (root / source).read_bytes()
        errs += _frontmatter_errors(name, content.decode("utf-8", errors="replace"))
        if not (root / copy).is_file():
            errs.append(f"{copy}  /  副本不存在（运行 uv run ppt sync-skill）")
        elif (root / copy).read_bytes() != content:
            errs.append(f"{copy}  /  与正本不一致（运行 uv run ppt sync-skill）")
    return errs
