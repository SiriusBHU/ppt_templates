"""Agent skill：正本在 .agents/skills，各家工具读的副本由 ppt sync-skill 复制，ppt validate 检查两者一致。"""

import shutil
from pathlib import Path

import yaml

from .errors import PptError

SKILL_NAME = "ppt-templates"
SOURCE = Path(".agents/skills") / SKILL_NAME / "SKILL.md"
# 需要和正本保持一致的副本。Claude Code 只读 .claude/skills，对软链的发现不稳定，所以放真实副本。
COPIES = [Path(".claude/skills") / SKILL_NAME / "SKILL.md"]
DESCRIPTION_MAX = 1024


def sync_skill(root: Path) -> list[Path]:
    """把正本复制到每个副本位置，返回写入的路径。"""
    if not (root / SOURCE).is_file():
        raise PptError(f"{SOURCE}  /  正本不存在")
    written = []
    for copy in COPIES:
        target = root / copy
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / SOURCE, target)
        written.append(target)
    return written


def _frontmatter_errors(text: str) -> list[str]:
    """正本的 frontmatter：name 与目录名一致，description 非空且不超过 1024 字。"""
    parts = text.split("---\n", 2) if text.startswith("---\n") else []
    if len(parts) < 3:
        return [f"{SOURCE}  /  缺少 frontmatter（文件开头应为 --- 包起来的 YAML）"]
    try:
        meta = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return [f"{SOURCE}  /  frontmatter 不是合法的 YAML：{e}"]
    if not isinstance(meta, dict):
        return [f"{SOURCE}  /  frontmatter 必须是键值对"]
    errs = []
    if meta.get("name") != SKILL_NAME:
        errs.append(f"{SOURCE}  /name  必须与目录名 {SKILL_NAME} 一致，实际是 {meta.get('name')!r}")
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        errs.append(f"{SOURCE}  /description  不能为空")
    elif len(description) > DESCRIPTION_MAX:
        errs.append(f"{SOURCE}  /description  长度 {len(description)}，超过上限 {DESCRIPTION_MAX}")
    return errs


def check_skill(root: Path) -> list[str]:
    """仓库里有 .agents/skills 才检查：正本存在且 frontmatter 合法，每个副本与正本逐字节一致。"""
    if not (root / ".agents" / "skills").is_dir():
        return []
    if not (root / SOURCE).is_file():
        return [f"{SOURCE}  /  正本不存在"]
    source = (root / SOURCE).read_bytes()
    errs = _frontmatter_errors(source.decode("utf-8", errors="replace"))
    for copy in COPIES:
        if not (root / copy).is_file():
            errs.append(f"{copy}  /  副本不存在（运行 uv run ppt sync-skill）")
        elif (root / copy).read_bytes() != source:
            errs.append(f"{copy}  /  与正本不一致（运行 uv run ppt sync-skill）")
    return errs
