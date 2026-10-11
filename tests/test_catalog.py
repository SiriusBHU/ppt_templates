from factories import mini_template
from ppt_templates.catalog import build_catalog, filter_catalog
from ppt_templates.validate import validate_repo


def test_catalog_entry_for_real_template(root):
    entry = next(e for e in build_catalog(root) if e["id"] == "solution.solution-arch-overview")
    assert entry == {
        "id": "solution.solution-arch-overview",
        "topic": "solution",
        "also_fits": ["system", "software", "hardware"],
        "name": "分区架构方案总览",
        "roles": ["solution", "feature"],
        "density": "talk",
        "level": "system",
        "tags": ["架构", "分区", "方案", "挑战", "关键技术"],
        "when_to_use": "用一页讲清系统方案的全貌：面临的核心挑战、设计理念、分区分层的整体架构，以及支撑它的关键技术",
        "slots": {
            "required": ["title", "takeaway", "challenges", "principles", "arch", "key_techs"],
            "optional": ["title_suffix"],
        },
    }


def test_filter_catalog():
    entries = [
        {"id": "system.a", "topic": "system", "also_fits": ["hardware"], "roles": ["solution"], "density": "talk", "tags": ["架构"]},
        {"id": "common.b", "topic": "common", "also_fits": [], "roles": ["summary"], "density": "read", "tags": []},
    ]
    ids = lambda **kw: [e["id"] for e in filter_catalog(entries, **kw)]
    assert ids(topic="hardware") == ["system.a"]
    assert ids(topic="common") == ["common.b"]
    assert ids(role="summary") == ["common.b"]
    assert ids(density="talk") == ["system.a"]
    assert ids(tag="架构") == ["system.a"]
    assert ids() == ["system.a", "common.b"]


def test_stale_catalog_is_an_error(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    assert validate_repo(repo).errors == []
    (repo / "catalog.json").write_text("[]\n", encoding="utf-8")
    assert validate_repo(repo).errors == ["catalog.json 不是最新的（运行 uv run ppt catalog）"]


def test_catalog_ignores_dot_directories(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    hidden = repo / "templates" / "common" / ".draft"
    hidden.mkdir()
    (hidden / "template.yaml").write_text("id: common.draft\n", encoding="utf-8")
    assert [e["id"] for e in build_catalog(repo)] == ["common.summary-note"]
