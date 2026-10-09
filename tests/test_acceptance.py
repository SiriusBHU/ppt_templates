"""把 bullets / table / block-diagram 三个演示模板渲染成 PNG（out/acceptance/），用于目视验收。"""

import shutil

import pytest

from factories import bullets_template, diagram_template, table_template
from ppt_templates.preview import render_pngs
from ppt_templates.render import render_deck

pytestmark = pytest.mark.skipif(shutil.which("soffice") is None, reason="需要 LibreOffice (soffice)")


def test_render_acceptance_pngs(make_repo, root):
    demos = {
        "common.summary-points": bullets_template(),
        "common.overview-table": table_template(),
        "system.solution-flow": diagram_template(),
    }
    repo = make_repo(demos)
    deck = {"style": "default", "pages": [{"template": tid, "data": example} for tid, (_, example) in demos.items()]}
    pngs = render_pngs(render_deck(deck, repo), root / "out" / "acceptance")
    assert [p.name for p in pngs] == ["slide-01.png", "slide-02.png", "slide-03.png"]
