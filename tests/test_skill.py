import re

import pytest
import yaml

from factories import mini_template
from ppt_templates.cli import main
from ppt_templates.errors import PptError
from ppt_templates.skill import COPIES, SOURCE, check_skill, sync_skill
from ppt_templates.slots import prepare_pages
from ppt_templates.validate import validate_repo

GOOD = '---\nname: ppt-templates\ndescription: "用页模板生成 pptx"\n---\n\n# 正文\n'
SYNC_HINT = "与正本不一致（运行 uv run ppt sync-skill）"


@pytest.fixture
def skill_repo(make_repo):
    """带 .agents/skills 的最小仓库：正本写好，副本已同步。"""
    repo = make_repo({"common.summary-note": mini_template()})
    (repo / SOURCE).parent.mkdir(parents=True)
    (repo / SOURCE).write_text(GOOD, encoding="utf-8")
    sync_skill(repo)
    return repo


def test_real_skill_is_valid_and_in_sync(root):
    assert check_skill(root) == []
    assert all((root / c).read_bytes() == (root / SOURCE).read_bytes() for c in COPIES)


def test_real_skill_example_deck_passes_validation(root):
    text = (root / SOURCE).read_text(encoding="utf-8")
    deck = yaml.safe_load(re.search(r"```yaml\n(.*?)```", text, re.S).group(1))
    assert len(prepare_pages(deck, root)) == len(deck["pages"])


def test_real_skill_body_is_short(root):
    assert len((root / SOURCE).read_text(encoding="utf-8").splitlines()) <= 150


def test_repo_without_agents_skills_is_not_checked(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    assert validate_repo(repo).errors == []


def test_synced_skill_repo_is_valid(skill_repo):
    assert validate_repo(skill_repo).errors == []


def test_sync_copies_source_to_every_target(skill_repo):
    (skill_repo / SOURCE).write_text(GOOD + "新增一行\n", encoding="utf-8")
    assert [p.relative_to(skill_repo) for p in sync_skill(skill_repo)] == list(COPIES)
    assert all((skill_repo / c).read_bytes() == (skill_repo / SOURCE).read_bytes() for c in COPIES)


def test_sync_without_source_is_an_error(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    with pytest.raises(PptError, match="正本不存在"):
        sync_skill(repo)


def test_stale_copy_is_an_error(skill_repo):
    (skill_repo / SOURCE).write_text(GOOD + "新增一行\n", encoding="utf-8")
    assert validate_repo(skill_repo).errors == [f"{COPIES[0]}  /  {SYNC_HINT}"]


def test_missing_copy_is_an_error(skill_repo):
    (skill_repo / COPIES[0]).unlink()
    assert validate_repo(skill_repo).errors == [f"{COPIES[0]}  /  副本不存在（运行 uv run ppt sync-skill）"]


def test_missing_source_is_an_error(skill_repo):
    (skill_repo / SOURCE).unlink()
    assert validate_repo(skill_repo).errors == [f"{SOURCE}  /  正本不存在"]


def frontmatter(**fields):
    body = yaml.safe_dump({"name": "ppt-templates", "description": "用页模板生成 pptx", **fields}, allow_unicode=True)
    return f"---\n{body}---\n\n正文\n"


@pytest.mark.parametrize("text, expected", [
    ("# 没有 frontmatter\n", "/  缺少 frontmatter"),
    ("---\nname: [oops\n---\n", "/  frontmatter 不是合法的 YAML"),
    ("---\n- a\n- b\n---\n", "/  frontmatter 必须是键值对"),
    (frontmatter(name="other"), "/name  必须与目录名 ppt-templates 一致，实际是 'other'"),
    (frontmatter(name=None), "/name  必须与目录名 ppt-templates 一致，实际是 None"),
    (frontmatter(description=""), "/description  不能为空"),
    (frontmatter(description=None), "/description  不能为空"),
    (frontmatter(description="长" * 1025), "/description  长度 1025，超过上限 1024"),
])
def test_frontmatter_rules(skill_repo, text, expected):
    (skill_repo / SOURCE).write_text(text, encoding="utf-8")
    sync_skill(skill_repo)
    errors = validate_repo(skill_repo).errors
    assert len(errors) == 1 and errors[0].startswith(f"{SOURCE}  {expected}")


def test_description_at_the_limit_is_valid(skill_repo):
    (skill_repo / SOURCE).write_text(frontmatter(description="长" * 1024), encoding="utf-8")
    sync_skill(skill_repo)
    assert validate_repo(skill_repo).errors == []


def test_cli_sync_skill(skill_repo, monkeypatch, capsys):
    (skill_repo / COPIES[0]).write_text("旧内容", encoding="utf-8")
    monkeypatch.chdir(skill_repo)
    assert main(["sync-skill"]) == 0
    assert capsys.readouterr().out.splitlines() == [str(COPIES[0])]
    assert (skill_repo / COPIES[0]).read_bytes() == (skill_repo / SOURCE).read_bytes()
