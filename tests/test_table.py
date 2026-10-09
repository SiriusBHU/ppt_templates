import pytest
from pptx import Presentation

from factories import deck_of, table_template
from ppt_templates.errors import PptError
from ppt_templates.render import render_deck
from ppt_templates.validate import validate_repo


def test_table_renders_native_table_with_header_and_highlight(make_repo, tmp_path):
    template, example = table_template()
    repo = make_repo({"common.overview-table": (template, example)})
    assert validate_repo(repo).errors == []
    path = tmp_path / "t.pptx"
    render_deck(deck_of("common.overview-table", example), repo).save(path)
    frame = next(sh for sh in Presentation(path).slides[0].shapes if sh.has_table)
    table = frame.table
    assert (len(table.rows), len(table.columns)) == (4, 4)
    assert frame._element.xpath(".//a:tableStyleId/text()") == ["{2D5ABB26-0587-4C30-8999-92F81FD0307C}"]
    assert table.columns[0].width == 200 * 9525
    assert str(table.cell(0, 1).fill.fore_color.rgb) == "1F3A5F"   # 表头
    assert str(table.cell(0, 2).fill.fore_color.rgb) == "EA7317"   # 高亮列的表头
    hot = table.cell(1, 2)
    assert str(hot.fill.fore_color.rgb) == "FFF1E6"
    assert hot.text_frame.paragraphs[0].runs[0].font.bold
    first = table.cell(1, 0)
    assert first.text == "带宽" and first.text_frame.paragraphs[0].runs[0].font.bold
    runs = frame._element.xpath(".//a:r")
    assert frame._element.xpath(".//a:r/a:rPr/a:ea/@typeface") == ["微软雅黑"] * len(runs)


def test_table_row_length_must_match_columns(make_repo):
    template, example = table_template()
    example["matrix"]["rows"][1] = ["延迟"]
    repo = make_repo({"common.overview-table": (template, example)})
    with pytest.raises(PptError, match="表格第 2 行有 1 格，表头有 4 列"):
        render_deck(deck_of("common.overview-table", example), repo)
