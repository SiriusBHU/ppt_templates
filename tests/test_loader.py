import pytest
import yaml

from factories import mini_template
from ppt_templates.cli import main
from ppt_templates.errors import PptError
from ppt_templates.loader import load_yaml, template_dirs
from ppt_templates.schemas import errors


def test_yaml_syntax_error_becomes_ppt_error(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("pages: [\n  - a: b\n  c", encoding="utf-8")
    with pytest.raises(PptError, match=rf"^{path}  /  YAML 语法错误："):
        load_yaml(path)


def test_cli_prints_yaml_syntax_error_instead_of_traceback(root, tmp_path, monkeypatch, capsys):
    path = tmp_path / "deck.yaml"
    path.write_text("pages: [", encoding="utf-8")
    monkeypatch.chdir(root)
    assert main(["validate", str(path)]) == 1
    assert "YAML 语法错误" in capsys.readouterr().err


def test_template_dirs_skips_dot_directories(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    for hidden in (repo / "templates" / ".git" / "objects", repo / "templates" / "common" / ".draft"):
        hidden.mkdir(parents=True)
        (hidden / "template.yaml").write_text(yaml.safe_dump({"id": "x"}), encoding="utf-8")
    assert [d.name for d in template_dirs(repo)] == ["summary-note"]


def test_yaml_booleans_follow_yaml_1_2(tmp_path):
    path = tmp_path / "b.yaml"
    path.write_text("no: 1\non: off\na: [true, True, TRUE, false, False, FALSE]\nb: [yes, No, ON, y, n]\n", encoding="utf-8")
    assert load_yaml(path) == {"no": 1, "on": "off", "a": [True, True, True, False, False, False],
                               "b": ["yes", "No", "ON", "y", "n"]}


def test_yes_is_a_string_and_fails_the_boolean_schema(tmp_path):
    path = tmp_path / "n.yaml"
    path.write_text("highlight: yes\n", encoding="utf-8")
    schema = {"type": "object", "properties": {"highlight": {"type": "boolean"}}}
    assert errors(schema, load_yaml(path)) == ["/highlight  类型应为 boolean"]
