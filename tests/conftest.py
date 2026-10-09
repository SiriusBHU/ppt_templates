import shutil
from pathlib import Path

import pytest
import yaml

from ppt_templates.catalog import write_catalog
from ppt_templates.loader import find_repo_root, load_example

TEMPLATE_ID = "system.solution-layered-arch"


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
    """在临时目录搭一个最小仓库：复制 taxonomy / schema / styles，再写入给定的模板。"""

    def make(templates: dict) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        shutil.copy(root / "taxonomy.yaml", repo / "taxonomy.yaml")
        shutil.copytree(root / "schema", repo / "schema")
        shutil.copytree(root / "styles", repo / "styles")
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
