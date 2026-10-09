"""对仓库里真实的模板做整体检查。"""

from ppt_templates.validate import validate_repo


def test_repository_is_valid(root):
    assert validate_repo(root).errors == []
