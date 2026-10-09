"""对仓库里真实的模板做整体检查：仓库校验无错，每个模板的 example 都能渲染。"""

import pytest
from pptx import Presentation

from factories import deck_of
from ppt_templates.loader import find_repo_root, load_example
from ppt_templates.render import render_deck
from ppt_templates.validate import validate_repo


def test_repository_is_valid(root):
    assert validate_repo(root).errors == []


def _template_ids(root):
    return [f"{p.parent.parent.name}.{p.parent.name}" for p in sorted((root / "templates").glob("*/*/template.yaml"))]


@pytest.mark.parametrize("tid", _template_ids(find_repo_root()))
def test_every_example_renders(root, tmp_path, tid):
    path = tmp_path / "out.pptx"
    render_deck(deck_of(tid, load_example(root, tid)), root).save(path)
    assert len(Presentation(path).slides) == 1
