"""taxonomy.yaml：主题与页功能的受控词表。"""

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import PptError
from .loader import load_yaml

ID = re.compile(r"^[a-z]+$")


@dataclass(frozen=True)
class Taxonomy:
    topics: dict[str, dict]  # id → 条目（name / includes / excludes）
    roles: dict[str, dict]   # id → 条目（name / question）


def check_taxonomy(raw: dict) -> list[str]:
    """id 必须是单个小写英文单词且不重复，每个条目都要有 name。"""
    errs = []
    for kind in ("topics", "roles"):
        seen = set()
        for i, entry in enumerate(raw.get(kind) or []):
            tid = entry.get("id")
            if not isinstance(tid, str) or not ID.match(tid):
                errs.append(f"taxonomy.yaml  /{kind}/{i}/id  {tid!r} 必须是单个小写英文单词")
            elif tid in seen:
                errs.append(f"taxonomy.yaml  /{kind}/{i}/id  重复的 id {tid}")
            seen.add(tid)
            if not entry.get("name"):
                errs.append(f"taxonomy.yaml  /{kind}/{i}/name  缺少名称")
        if not raw.get(kind):
            errs.append(f"taxonomy.yaml  /{kind}  不能为空")
    return errs


def load_taxonomy(root: Path) -> Taxonomy:
    raw = load_yaml(root / "taxonomy.yaml")
    errs = check_taxonomy(raw)
    if errs:
        raise PptError("\n".join(errs))
    return Taxonomy({t["id"]: t for t in raw["topics"]}, {r["id"]: r for r in raw["roles"]})
