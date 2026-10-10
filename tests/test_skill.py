import re

import pytest
import yaml

from factories import mini_template
from ppt_templates.cli import main
from ppt_templates.errors import PptError
from ppt_templates.skill import SKILLS, check_skill, copy_path, source_path, sync_skill
from ppt_templates.slots import prepare_pages
from ppt_templates.validate import validate_repo

FIRST, SECOND = SKILLS
SYNC_HINT = "与正本不一致（运行 uv run ppt sync-skill）"


def good(name):
    return f'---\nname: {name}\ndescription: "用页模板生成 pptx"\n---\n\n# 正文\n'


@pytest.fixture
def skill_repo(make_repo):
    """带 .agents/skills 的最小仓库：每个 skill 的正本写好，副本已同步。"""
    repo = make_repo({"common.summary-note": mini_template()})
    for name in SKILLS:
        (repo / source_path(name)).parent.mkdir(parents=True)
        (repo / source_path(name)).write_text(good(name), encoding="utf-8")
    sync_skill(repo)
    return repo


def test_real_skills_are_valid_and_in_sync(root):
    assert check_skill(root) == []
    assert all((root / copy_path(n)).read_bytes() == (root / source_path(n)).read_bytes() for n in SKILLS)


def test_real_skill_example_deck_passes_validation(root):
    text = (root / source_path(FIRST)).read_text(encoding="utf-8")
    deck = yaml.safe_load(re.search(r"```yaml\n(.*?)```", text, re.S).group(1))
    assert len(prepare_pages(deck, root)) == len(deck["pages"])


@pytest.mark.parametrize("name", SKILLS)
def test_real_skill_body_is_short(root, name):
    assert len((root / source_path(name)).read_text(encoding="utf-8").splitlines()) <= 150


def test_repo_without_agents_skills_is_not_checked(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    assert validate_repo(repo).errors == []


def test_synced_skill_repo_is_valid(skill_repo):
    assert validate_repo(skill_repo).errors == []


def test_sync_copies_every_source_to_its_target(skill_repo):
    for name in SKILLS:
        (skill_repo / source_path(name)).write_text(good(name) + "新增一行\n", encoding="utf-8")
    assert [p.relative_to(skill_repo) for p in sync_skill(skill_repo)] == [copy_path(n) for n in SKILLS]
    assert all((skill_repo / copy_path(n)).read_bytes() == (skill_repo / source_path(n)).read_bytes() for n in SKILLS)


def test_sync_without_source_is_an_error(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    with pytest.raises(PptError, match="正本不存在"):
        sync_skill(repo)


def test_sync_with_one_source_missing_writes_nothing(skill_repo):
    (skill_repo / copy_path(FIRST)).unlink()
    (skill_repo / source_path(SECOND)).unlink()
    with pytest.raises(PptError, match=re.escape(f"{source_path(SECOND)}  /  正本不存在")):
        sync_skill(skill_repo)
    assert not (skill_repo / copy_path(FIRST)).exists()


@pytest.mark.parametrize("name", SKILLS)
def test_stale_copy_is_an_error(skill_repo, name):
    (skill_repo / source_path(name)).write_text(good(name) + "新增一行\n", encoding="utf-8")
    assert validate_repo(skill_repo).errors == [f"{copy_path(name)}  /  {SYNC_HINT}"]


@pytest.mark.parametrize("name", SKILLS)
def test_missing_copy_is_an_error(skill_repo, name):
    (skill_repo / copy_path(name)).unlink()
    assert validate_repo(skill_repo).errors == [f"{copy_path(name)}  /  副本不存在（运行 uv run ppt sync-skill）"]


@pytest.mark.parametrize("name", SKILLS)
def test_missing_source_is_an_error(skill_repo, name):
    (skill_repo / source_path(name)).unlink()
    assert validate_repo(skill_repo).errors == [f"{source_path(name)}  /  正本不存在"]


def frontmatter(**fields):
    body = yaml.safe_dump({"name": FIRST, "description": "用页模板生成 pptx", **fields}, allow_unicode=True)
    return f"---\n{body}---\n\n正文\n"


@pytest.mark.parametrize("text, expected", [
    ("# 没有 frontmatter\n", "/  缺少 frontmatter"),
    ("---\nname: [oops\n---\n", "/  frontmatter 不是合法的 YAML"),
    ("---\n- a\n- b\n---\n", "/  frontmatter 必须是键值对"),
    (frontmatter(name="other"), f"/name  必须与目录名 {FIRST} 一致，实际是 'other'"),
    (frontmatter(name=None), f"/name  必须与目录名 {FIRST} 一致，实际是 None"),
    (frontmatter(description=""), "/description  不能为空"),
    (frontmatter(description=None), "/description  不能为空"),
    (frontmatter(description="长" * 1025), "/description  长度 1025，超过上限 1024"),
])
def test_frontmatter_rules(skill_repo, text, expected):
    (skill_repo / source_path(FIRST)).write_text(text, encoding="utf-8")
    sync_skill(skill_repo)
    errors = validate_repo(skill_repo).errors
    assert len(errors) == 1 and errors[0].startswith(f"{source_path(FIRST)}  {expected}")


def test_skill_name_must_match_its_own_directory(skill_repo):
    (skill_repo / source_path(SECOND)).write_text(good(FIRST), encoding="utf-8")
    sync_skill(skill_repo)
    assert validate_repo(skill_repo).errors == [
        f"{source_path(SECOND)}  /name  必须与目录名 {SECOND} 一致，实际是 {FIRST!r}"]


def test_description_at_the_limit_is_valid(skill_repo):
    (skill_repo / source_path(FIRST)).write_text(frontmatter(description="长" * 1024), encoding="utf-8")
    sync_skill(skill_repo)
    assert validate_repo(skill_repo).errors == []


def test_cli_sync_skill(skill_repo, monkeypatch, capsys):
    for name in SKILLS:
        (skill_repo / copy_path(name)).write_text("旧内容", encoding="utf-8")
    monkeypatch.chdir(skill_repo)
    assert main(["sync-skill"]) == 0
    assert capsys.readouterr().out.splitlines() == [str(copy_path(n)) for n in SKILLS]
    assert all((skill_repo / copy_path(n)).read_bytes() == (skill_repo / source_path(n)).read_bytes() for n in SKILLS)
