"""ppt 命令行：render / preview。"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .errors import PptError
from .loader import find_repo_root, load_deck, load_example, template_dir
from .preview import render_pngs
from .render import render_deck


def _render(args) -> None:
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    render_deck(load_deck(Path(args.deck)), find_repo_root()).save(out)
    print(out)


def _preview(args) -> None:
    root = find_repo_root()
    if Path(args.target).suffix in (".yaml", ".yml"):
        if args.write or args.style:
            raise PptError("--write / --style 只用于模板 id，不用于 deck 文件")
        deck = load_deck(Path(args.target))
    else:
        deck = {"style": args.style or "default",
                "pages": [{"template": args.target, "data": load_example(root, args.target)}]}
    prs = render_deck(deck, root)

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

    args = parser.parse_args(argv)
    try:
        args.run(args)
    except PptError as e:
        print(e, file=sys.stderr)
        return 1
    return 0
