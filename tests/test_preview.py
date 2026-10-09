import shutil

import pytest
from PIL import Image

from ppt_templates.cli import main

pytestmark = pytest.mark.skipif(shutil.which("soffice") is None, reason="需要 LibreOffice (soffice)")


def test_preview_template_id_writes_one_1920_wide_png_per_slide(tmp_path, monkeypatch, root):
    monkeypatch.chdir(root)
    assert main(["preview", "system.solution-layered-arch", "-o", str(tmp_path)]) == 0
    pngs = sorted(tmp_path.glob("slide-*.png"))
    assert [p.name for p in pngs] == ["slide-01.png"]
    with Image.open(pngs[0]) as img:
        assert img.size == (1920, 1080)
