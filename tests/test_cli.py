import yaml

from factories import mini_template
from ppt_templates.cli import main


def test_validate_repo_ok(root, monkeypatch, capsys):
    monkeypatch.chdir(root)
    assert main(["validate"]) == 0
    assert "校验通过" in capsys.readouterr().out


def test_validate_repo_reports_errors(make_repo, monkeypatch, capsys):
    repo = make_repo({"common.summary-note": mini_template(roles=["risk"])})
    monkeypatch.chdir(repo)
    assert main(["validate"]) == 1
    assert "必须以主页功能 risk- 开头" in capsys.readouterr().err


def test_validate_deck(deck, tmp_path, monkeypatch, root, capsys):
    path = tmp_path / "deck.yaml"
    path.write_text(yaml.safe_dump(deck, allow_unicode=True), encoding="utf-8")
    monkeypatch.chdir(root)
    assert main(["validate", str(path)]) == 0
    assert "deck 校验通过：1 页" in capsys.readouterr().out
    deck["style"] = "nope"
    path.write_text(yaml.safe_dump(deck, allow_unicode=True), encoding="utf-8")
    assert main(["validate", str(path)]) == 1
    assert "文件不存在" in capsys.readouterr().err


def test_list_and_show(make_repo, monkeypatch, capsys):
    repo = make_repo({"common.summary-note": mini_template()})
    monkeypatch.chdir(repo)
    assert main(["list", "--role", "summary"]) == 0
    assert capsys.readouterr().out == "common.summary-note\t一句话总结\tsummary\t用一句话总结全文\n"
    assert main(["show", "common.summary-note"]) == 0
    out = capsys.readouterr().out
    assert "# ---- template.yaml ----" in out and "# ---- example.yaml ----" in out and "一句话说清楚结论" in out
