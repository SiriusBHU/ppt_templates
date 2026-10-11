import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from ppt_templates.catalog import write_catalog
from ppt_templates.loader import find_repo_root, load_example

TEMPLATE_ID = "solution.solution-arch-overview"


def _can_symlink() -> bool:
    """Windows 上普通用户默认不能建符号链接（WinError 1314）。"""
    with tempfile.TemporaryDirectory() as d:
        try:
            (Path(d) / "link").symlink_to(Path(d) / "target")
        except OSError:
            return False
    return True


CAN_SYMLINK = _can_symlink()
needs_symlink = pytest.mark.skipif(not CAN_SYMLINK, reason="需要建符号链接的权限（Windows 上要开开发者模式或用管理员运行）")


@pytest.fixture(scope="session")
def root():
    return find_repo_root()


@pytest.fixture
def deck(root):
    return {"style": "default", "pages": [{"template": TEMPLATE_ID, "data": load_example(root, TEMPLATE_ID)}]}


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


@pytest.fixture
def make_repo(root, tmp_path):
    """在临时目录搭一个最小仓库：复制 taxonomy / schema / styles，再写入给定的模板。
    测试模板大多没有 takeaway 槽位，会落到风格的 body_compact；默认把它从复制的默认风格里去掉（回落到 body），
    让几何断言按固定的 body 原点写。要测紧凑页框就传 compact_body=True。"""

    def make(templates: dict, compact_body: bool = False) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        shutil.copy(root / "taxonomy.yaml", repo / "taxonomy.yaml")
        shutil.copytree(root / "schema", repo / "schema")
        shutil.copytree(root / "styles", repo / "styles")
        if not compact_body:
            style_path = repo / "styles" / "default" / "style.yaml"
            lines = style_path.read_text(encoding="utf-8").splitlines(keepends=True)
            style_path.write_text("".join(line for line in lines if not line.startswith("  body_compact:")), encoding="utf-8")
        for tid, (template, example) in templates.items():
            topic, name = tid.split(".", 1)
            d = repo / "templates" / topic / name
            d.mkdir(parents=True)
            _dump(d / "template.yaml", template)
            if example is not None:
                _dump(d / "example.yaml", example)
        write_catalog(repo)
        return repo

    return make
