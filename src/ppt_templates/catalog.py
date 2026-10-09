"""catalog.json：所有模板的精简索引（spec 7.2），由 ppt catalog 生成并提交到仓库。"""

import json
from pathlib import Path

from .errors import PptError
from .loader import load_yaml, template_dirs


def build_catalog(root: Path) -> list[dict]:
    entries = []
    for tdir in template_dirs(root):
        path = tdir / "template.yaml"
        if not path.is_file():
            continue  # 缺少 template.yaml 由 ppt validate 报告
        tpl = load_yaml(path)
        slots = tpl["slots"]
        required = list(slots.get("required", []))
        entry = {
            "id": tpl["id"],
            "topic": path.parent.parent.name,
            "also_fits": tpl.get("also_fits", []),
            "name": tpl["name"],
            "roles": tpl["roles"],
            "density": tpl.get("density", "talk"),
        }
        if "level" in tpl:
            entry["level"] = tpl["level"]
        entry["tags"] = tpl.get("tags", [])
        entry["when_to_use"] = tpl["when_to_use"]
        entry["slots"] = {
            "required": required,
            "optional": [k for k in slots.get("properties", {}) if k not in required],
        }
        entries.append(entry)
    return entries


def catalog_text(root: Path) -> str:
    return json.dumps(build_catalog(root), ensure_ascii=False, indent=2) + "\n"


def write_catalog(root: Path) -> Path:
    path = root / "catalog.json"
    path.write_text(catalog_text(root), encoding="utf-8")
    return path


def catalog_is_current(root: Path) -> bool:
    path = root / "catalog.json"
    return path.is_file() and path.read_text(encoding="utf-8") == catalog_text(root)


def load_catalog(root: Path) -> list[dict]:
    path = root / "catalog.json"
    if not path.is_file():
        raise PptError("catalog.json 不存在，先运行 uv run ppt catalog")
    return json.loads(path.read_text(encoding="utf-8"))


def filter_catalog(entries, topic=None, role=None, density=None, tag=None) -> list[dict]:
    """按条件筛选；topic 同时匹配主题和 also_fits，未给的条件不参与筛选。"""
    def keep(e):
        return ((topic is None or topic == e["topic"] or topic in e["also_fits"])
                and (role is None or role in e["roles"])
                and (density is None or density == e["density"])
                and (tag is None or tag in e["tags"]))

    return [e for e in entries if keep(e)]
