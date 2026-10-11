"""pptx → PDF（soffice）→ 每页一张 PNG（pypdfium2）。不能用 soffice --convert-to png，它只输出第一页。"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pypdfium2 as pdfium
from pptx import Presentation

from .errors import PptError
from .loader import FONT

# 本机多半没有微软雅黑；不指定替换时 LibreOffice 每次回退的字体都不一样（甚至是衬线体），
# 预览图会失真。这里在一次性配置里把微软雅黑固定替换为本机的黑体，只影响预览，不影响 pptx。
PREVIEW_FONT = "Hiragino Sans GB"  # macOS 自带，粗体正常
_SUBSTITUTION_XCU = f"""<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Font/Substitution"><prop oor:name="Replacement" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Font/Substitution/FontPairs"><node oor:name="_0" oor:op="replace">
<prop oor:name="Always" oor:op="fuse"><value>true</value></prop>
<prop oor:name="OnScreenOnly" oor:op="fuse"><value>false</value></prop>
<prop oor:name="ReplaceFont" oor:op="fuse"><value>{FONT}</value></prop>
<prop oor:name="SubstituteFont" oor:op="fuse"><value>{PREVIEW_FONT}</value></prop>
</node></item>
</oor:items>
"""


SOFFICE_PATHS = (
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


def find_soffice() -> str | None:
    """先找 PATH，再找各平台的默认安装位置（Windows 装 LibreOffice 不会加进 PATH）。"""
    if found := shutil.which("soffice"):
        return found
    return next((p for p in SOFFICE_PATHS if Path(p).is_file()), None)


def render_pngs(prs: Presentation, out_dir: Path, width: int = 1920) -> list[Path]:
    soffice = find_soffice()
    if not soffice:
        raise PptError("找不到 soffice：预览依赖 LibreOffice，请先安装（macOS: brew install --cask libreoffice；"
                       "Windows: winget install TheDocumentFoundation.LibreOffice）")
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        prs.save(tmp / "deck.pptx")
        (tmp / "profile" / "user").mkdir(parents=True)
        if sys.platform != "win32":  # Windows 自带微软雅黑，不用替换（也没有冬青黑体可换）
            (tmp / "profile" / "user" / "registrymodifications.xcu").write_text(_SUBSTITUTION_XCU, encoding="utf-8")
        proc = subprocess.run(
            [soffice, f"-env:UserInstallation={(tmp / 'profile').as_uri()}", "--headless",
             "--convert-to", "pdf", "--outdir", str(tmp), str(tmp / "deck.pptx")],
            capture_output=True, text=True, timeout=300,
        )
        pdf_path = tmp / "deck.pdf"
        if proc.returncode != 0 or not pdf_path.is_file():
            raise PptError(f"soffice 转换 PDF 失败（退出码 {proc.returncode}）:\n{proc.stderr or proc.stdout}")
        pdf = pdfium.PdfDocument(str(pdf_path))
        try:
            paths = []
            for i, page in enumerate(pdf, 1):
                path = out_dir / f"slide-{i:02d}.png"
                page.render(scale=width / page.get_width()).to_pil().save(path)
                paths.append(path)
            return paths
        finally:
            pdf.close()
