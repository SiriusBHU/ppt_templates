"""ppt mcp：stdio MCP server。工具复用 CLI 用到的同一批函数，这里只做参数检查和返回格式的适配。"""

import functools
import re
import tempfile
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from .catalog import filter_catalog, load_catalog
from .errors import PptError
from .images import ImageSource
from .loader import find_repo_root, load_example, load_style, load_template
from .preview import render_pngs
from .render import render_deck as build_presentation
from .slots import prepare_pages
from .taxonomy import load_taxonomy

PREVIEW_WIDTH = 1280
FILENAME = re.compile(r"[^/\\\0]+\.pptx")
TEMPLATE_ID = re.compile(r"[a-z]+\.[a-z0-9]+(-[a-z0-9]+)*")  # 与 schema/deck.schema.json 里的模板 id 格式一致

mcp = MCPServer(
    "ppt-templates",
    instructions="页粒度 PPT 模板库。流程：get_taxonomy / list_templates 挑模板 → get_template 读槽位和写作要点 → "
                 "按槽位写 deck → validate_deck 校验并按报错修改 → render_deck 生成 .pptx → preview_deck 看排版。",
)


def tool(fn):
    """注册为 MCP 工具。PptError 转成 ToolError：MCPServer 只会把 ToolError 的消息交给调用方，其他异常一律只返回通用错误。
    函数本身原样返回，直接调用时仍抛 PptError。"""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PptError as e:
            raise ToolError(str(e)) from e

    mcp.tool()(wrapper)
    return fn


@tool
def get_taxonomy() -> dict[str, Any]:
    """返回模板库的主题（topics）和页功能（roles）。主题说明一页讲的是什么对象，页功能说明这一页在叙事中的作用，
    其中 question 是该页要回答的问题。先用它排出每一页的页功能顺序。"""
    tax = load_taxonomy(find_repo_root())
    return {"topics": list(tax.topics.values()), "roles": list(tax.roles.values())}


@tool
def list_templates(topic: str | None = None, role: str | None = None, density: str | None = None,
                   tag: str | None = None) -> list[dict[str, Any]]:
    """列出页模板的精简索引（id、名称、页功能、适用场景、必填和可选槽位），可按条件筛选，不给的条件不参与筛选。
    topic 是主题，同时匹配模板声明的 also_fits；role 是页功能；density 取 talk（现场讲）或 read（供阅读）；tag 是标签。"""
    return filter_catalog(load_catalog(find_repo_root()), topic, role, density, tag)


@tool
def get_template(template_id: str) -> dict[str, Any]:
    """返回一个页模板的元数据、slots（内容的 JSON Schema，字段、必填、长度和数量上限都在里面）、guidance（写作要点）
    和 example（示例内容）。template_id 形如 system.solution-arch-overview。写这一页的 data 之前先读它。"""
    if not TEMPLATE_ID.fullmatch(template_id):
        raise PptError(f"模板 id 应为 <主题>.<名称>: {template_id!r}")
    root = find_repo_root()
    try:
        template = load_template(root, template_id)
    except PptError:
        raise PptError(f"模板 {template_id} 不存在") from None
    template.pop("layout", None)  # 写内容用不到版式坐标，还占 token
    return {**template, "example": load_example(root, template_id)}


def _images(root: Path) -> ImageSource:
    """deck 里 image 槽位的图片路径：相对仓库根目录解析，并且只能引用仓库之内的文件（符号链接解析后也要在仓库内）。
    deck 来自 MCP 客户端，不能让它借图片路径把仓库之外的文件读进 .pptx 或预览图。"""
    return ImageSource(root, confine=root)


def _deck_errors(deck: dict, root: Path) -> list[str]:
    try:
        prepare_pages(deck, root, _images(root))
        load_style(root, deck.get("style", "default"))
    except PptError as e:
        return str(e).splitlines()
    return []


@tool
def validate_deck(deck: dict[str, Any]) -> dict[str, Any]:
    """校验一份 deck，返回 {"ok": 是否通过, "errors": [中文错误]}。每条错误形如「第 N 页 <模板 id>  <JSON Pointer>  <消息>」，
    按消息修改后再校验。deck 的结构是 {"style": "default", "pages": [{"template": "<模板 id>", "data": {按 slots 填写的内容}}]}。
    图片槽位填图片路径：相对仓库根目录，只能引用仓库内的 png / jpg / jpeg / gif / bmp / tiff 文件；不填则画占位框。"""
    errors = _deck_errors(deck, find_repo_root())
    return {"ok": not errors, "errors": errors}


@tool
def render_deck(deck: dict[str, Any], filename: str = "deck.pptx") -> str:
    """把 deck 渲染成原生 .pptx，写入仓库的 out/ 目录，返回文件的绝对路径。会先校验，不通过就报错。
    filename 只能是文件名，不能含路径分隔符，且以 .pptx 结尾。图片槽位的路径规则同 validate_deck。"""
    if not FILENAME.fullmatch(filename):
        raise PptError(f"文件名 {filename!r} 不合法：必须是不含路径分隔符、以 .pptx 结尾的文件名（文件只会写入 out/ 目录）")
    root = find_repo_root()
    prs = build_presentation(deck, root, _images(root))
    out = root / "out"
    out.mkdir(exist_ok=True)
    path = out / filename
    prs.save(path)
    return str(path.resolve())


@tool
def preview_deck(deck: dict[str, Any]) -> list[Image]:
    """渲染 deck 并把每页转成一张 PNG 图片（宽 1280）返回，用来目视检查文字溢出、留白和对齐。需要本机安装 LibreOffice（soffice）。图片槽位的路径规则同 validate_deck。"""
    root = find_repo_root()
    prs = build_presentation(deck, root, _images(root))
    with tempfile.TemporaryDirectory() as tmp:
        return [Image(data=png.read_bytes(), format="png") for png in render_pngs(prs, Path(tmp), width=PREVIEW_WIDTH)]


def serve() -> None:
    mcp.run("stdio")
