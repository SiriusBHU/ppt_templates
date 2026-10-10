"""ppt 命令行：render / preview / validate / catalog / list / show / import / sync-skill / mcp。"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .catalog import filter_catalog, load_catalog, write_catalog
from .errors import PptError
from .images import ImageSource
from .importer import import_skeleton
from .loader import find_repo_root, load_deck, load_example, load_style, template_dir, template_dirs
from .preview import render_pngs
from .render import render_deck
from .skill import sync_skill
from .slots import prepare_pages
from .validate import validate_repo


def _render(args) -> None:
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    deck_path = Path(args.deck)
    render_deck(load_deck(deck_path), find_repo_root(), ImageSource(deck_path.resolve().parent)).save(out)
    print(out)


def _preview(args) -> None:
    root = find_repo_root()
    if Path(args.target).suffix in (".yaml", ".yml"):
        if args.write or args.style:
            raise PptError("--write / --style 只用于模板 id，不用于 deck 文件")
        deck = load_deck(Path(args.target))
        images = ImageSource(Path(args.target).resolve().parent)
    else:
        deck = {"style": args.style or "default",
                "pages": [{"template": args.target, "data": load_example(root, args.target)}]}
        images = ImageSource(template_dir(root, args.target))  # example.yaml 里的图片路径相对模板目录
    prs = render_deck(deck, root, images)

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(args.output or (tmp if args.write else "preview"))
        pngs = render_pngs(prs, out_dir)
        if args.write:
            target = template_dir(root, args.target) / "preview.png"
            shutil.copyfile(pngs[0], target)
            print(target)
        if args.output or not args.write:
            for png in pngs:
                print(png)


def _validate(args) -> None:
    root = find_repo_root()
    if args.deck:
        deck_path = Path(args.deck)
        deck = load_deck(deck_path)
        pages = prepare_pages(deck, root, ImageSource(deck_path.resolve().parent))
        load_style(root, deck.get("style", "default"))
        print(f"deck 校验通过：{len(pages)} 页")
        return
    report = validate_repo(root)
    for warning in report.warnings:
        print(f"警告  {warning}", file=sys.stderr)
    if report.errors:
        raise PptError("\n".join(report.errors))
    print(f"校验通过：{len(template_dirs(root))} 个模板")


def _catalog(args) -> None:
    print(write_catalog(find_repo_root()))


def _list(args) -> None:
    for e in filter_catalog(load_catalog(find_repo_root()), args.topic, args.role, args.density, args.tag):
        print(f"{e['id']}\t{e['name']}\t{','.join(e['roles'])}\t{e['when_to_use']}")


def _show(args) -> None:
    d = template_dir(find_repo_root(), args.id)
    for name in ("template.yaml", "example.yaml"):
        path = d / name
        if not path.is_file():
            raise PptError(f"模板 {args.id} 缺少 {name}")
        print(f"# ---- {name} ----")
        print(path.read_text(encoding="utf-8").rstrip())


def _import(args) -> None:
    dirs, warnings = import_skeleton(find_repo_root(), Path(args.skeleton), Path(args.output), args.slide)
    for warning in warnings:
        print(f"警告  {warning}", file=sys.stderr)
    for d in dirs:
        print(d)


def _sync_skill(args) -> None:
    root = find_repo_root()
    for path in sync_skill(root):
        print(path.relative_to(root))


def _mcp(args) -> None:
    from .mcp_server import serve  # mcp SDK 导入较慢，只在启动 server 时才加载

    serve()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="ppt", description="页粒度 PPT 模板渲染器")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("render", help="deck.yaml → .pptx")
    p.add_argument("deck")
    p.add_argument("-o", "--output", required=True, help="输出的 .pptx 路径")
    p.set_defaults(run=_render)

    p = sub.add_parser("preview", help="deck.yaml 或模板 id → 每页一张 PNG")
    p.add_argument("target", help="deck.yaml 路径，或 <主题>.<模板名>（用 example.yaml 渲染）")
    p.add_argument("-o", "--output", help="PNG 输出目录（默认 ./preview；模板 id 加 --write 时默认不额外输出）")
    p.add_argument("--style", help="仅模板 id：风格名，默认 default")
    p.add_argument("--write", action="store_true", help="仅模板 id：把第一页写入模板目录的 preview.png")
    p.set_defaults(run=_preview)

    p = sub.add_parser("validate", help="校验整个仓库；给出 deck.yaml 时只校验这份 deck")
    p.add_argument("deck", nargs="?")
    p.set_defaults(run=_validate)

    p = sub.add_parser("catalog", help="重新生成 catalog.json")
    p.set_defaults(run=_catalog)

    p = sub.add_parser("list", help="列出模板（读 catalog.json）")
    p.add_argument("--topic", help="主题；同时匹配 also_fits")
    p.add_argument("--role", help="页功能")
    p.add_argument("--density", choices=["talk", "read"])
    p.add_argument("--tag")
    p.set_defaults(run=_list)

    p = sub.add_parser("show", help="输出模板定义和示例内容")
    p.add_argument("id", help="<主题>.<模板名>")
    p.set_defaults(run=_show)

    p = sub.add_parser("import", help="骨架 pptx → 每页的 shapes.yaml 草稿和 original.png，供照着写模板")
    p.add_argument("skeleton", help="骨架 .pptx；同目录的 manifest.yaml 里的 purpose 会写进 shapes.yaml")
    p.add_argument("--slide", type=int, nargs="+", action="extend", metavar="N", help="只导这几页（从 1 起），默认全部")
    p.add_argument("-o", "--output", required=True, help="输出目录，每页写到 <目录>/slide-<N>/")
    p.set_defaults(run=_import)

    p = sub.add_parser("sync-skill", help="把 .agents/skills 里的 skill 正本复制到各工具读取的位置")
    p.set_defaults(run=_sync_skill)

    p = sub.add_parser("mcp", help="启动 stdio MCP server")
    p.set_defaults(run=_mcp)

    args = parser.parse_args(argv)
    try:
        args.run(args)
    except PptError as e:
        print(e, file=sys.stderr)
        return 1
    return 0
