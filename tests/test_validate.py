import pytest

from factories import mini_template
from ppt_templates.taxonomy import check_taxonomy
from ppt_templates.validate import validate_repo

F = "templates/common/summary-note/template.yaml"


def test_taxonomy_ids_must_be_single_lowercase_words_and_unique():
    raw = {
        "topics": [{"id": "system", "name": "系统"}, {"id": "system", "name": "重复"}],
        "roles": [{"id": "next-steps", "name": "下一步"}],
    }
    assert check_taxonomy(raw) == [
        "taxonomy.yaml  /topics/1/id  重复的 id system",
        "taxonomy.yaml  /roles/0/id  'next-steps' 必须是单个小写英文单词",
    ]


def test_mini_template_is_valid(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    assert validate_repo(repo).errors == []


@pytest.mark.parametrize("overrides, expected", [
    ({"id": "common.other"}, "/id  应为 common.summary-note（由目录决定），实际是 common.other"),
    ({"roles": ["nope"]}, "/roles/0  页功能 nope 不在 taxonomy.yaml 中"),
    ({"roles": ["risk"]}, "/roles/0  目录名 summary-note 必须以主页功能 risk- 开头"),
    ({"density": "read"}, "/density  目录名以 -read 结尾，当且仅当 density: read"),
    ({"also_fits": ["common"]}, "/also_fits/0  不能包含模板自己的主题"),
    ({"also_fits": ["galaxy"]}, "/also_fits/0  主题 galaxy 不在 taxonomy.yaml 中"),
    ({"level": "module"}, "/level  level 只用于 hardware、software、system 主题"),
    ({"layout": [{"type": "text", "box": [0, 0, 10, 10], "bind": "note", "style": "body", "size": 13}]},
     "/layout/0  不允许的字段 size"),
    ({"frame": "wide"}, "/frame  取值 wide 不在可选范围 ['standard', 'none']"),
])
def test_template_metadata_rules(make_repo, overrides, expected):
    repo = make_repo({"common.summary-note": mini_template(**overrides)})
    assert f"{F}  {expected}" in validate_repo(repo).errors


def test_unknown_topic_directory(make_repo):
    repo = make_repo({"galaxy.summary-note": mini_template(id="galaxy.summary-note")})
    assert "templates/galaxy/summary-note/template.yaml  /  主题目录 galaxy 不在 taxonomy.yaml 中" in validate_repo(repo).errors


def test_slots_must_be_an_object_schema(make_repo):
    repo = make_repo({"common.summary-note": mini_template(slots={"type": "array"})})
    assert f"{F}  /slots/type  顶层必须是 type: object" in validate_repo(repo).errors


def test_missing_example_is_an_error_and_missing_preview_a_warning(make_repo):
    template, _ = mini_template()
    repo = make_repo({"common.summary-note": (template, None)})
    report = validate_repo(repo)
    assert "templates/common/summary-note  缺少 example.yaml" in report.errors
    assert report.warnings == ["templates/common/summary-note  缺少 preview.png（运行 uv run ppt preview common.summary-note --write）"]
