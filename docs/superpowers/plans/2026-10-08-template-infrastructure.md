# 模板铺开基础设施 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐大规模编写模板所需的基础设施：仓库级校验、模板索引与检索命令、`bullets` 元素、`table` 和 `block-diagram` 组件，让后续批量写模板时有工具兜底。

**Architecture:** 所有结构约束写成 `schema/*.schema.json`（JSON Schema Draft 2020-12），由一个公共模块统一加载并输出中文错误；语义约束（命名、绑定、几何、token、catalog 是否最新）放在 `validate.py`。组件改为「渲染函数 + 数据 Schema」注册，校验器用组件 Schema 检查模板的 `example.yaml`。CLI 新增 `validate / catalog / list / show`。

**Tech Stack:** Python 3.13、uv、python-pptx、jsonschema、PyYAML、pypdfium2、pytest；预览依赖 LibreOffice（`soffice`）。

## Global Constraints

- 设计依据：`docs/superpowers/specs/2026-10-08-ppt-template-repo-design.md`；仓库规则：`AGENTS.md`。
- 画布固定 1280×720 逻辑像素；1px = 9525 EMU；幻灯片尺寸 12192000×6858000 EMU。
- `frame: standard` 的 layout 坐标以 body 区左上角为原点，参考尺寸 1216×560；`frame: none` 以画布为原点。
- 所有文字 run 的 `a:latin` / `a:ea` / `a:cs` 都是「微软雅黑」。
- 文字样式 token 与字号固定，所有模板、所有风格统一：`title` 24、`title_suffix` 18、`subtitle` 18、`emphasis` 14、`body` 12、`body_strong` 12、`detail` 10、`caption` 9、`footnote` 8、`kpi` 24。
- 颜色 token 固定：`primary`、`accent`、`text`、`muted`、`line`、`surface`、`bg`、`on_primary`、`highlight`、`highlight_strong`。
- 模板元素只能通过 token 引用颜色和文字样式，不能写色值、字号、字体。
- 上下左右页边距统一 32px；不画页码、数据来源、顶部色条。
- 主题 id、页功能 id 符合 `^[a-z]+$`；模板目录名 = `<roles[0]>-<形态>`；目录名以 `-read` 结尾当且仅当 `density: read`。
- 只做中文；`maxLength` 按中文字符计。
- 面向用户的错误信息用中文，格式为 `<文件或页>  <JSON Pointer>  <消息>`（两个空格分隔）。
- 运行测试：`uv run pytest`；单个测试：`uv run pytest tests/<file>.py::<name> -v`。
- 每次提交信息末尾加一行 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`（下文用第二个 `-m` 参数实现）。

## 文件结构

| 文件 | 职责 | 任务 |
|---|---|---|
| `src/ppt_templates/schemas.py`（新） | 加载 `schema/*.schema.json`；把 JSON Schema 错误格式化成中文 | 1 |
| `schema/deck.schema.json`（新） | deck 结构 | 1 |
| `schema/style.schema.json`（新） | 风格结构；固定字体、token 集合与字号 | 2 |
| `schema/template.schema.json`（新） | 模板结构；各布局元素允许的字段 | 3 |
| `src/ppt_templates/taxonomy.py`（新） | 读取并检查 `taxonomy.yaml` | 3 |
| `src/ppt_templates/validate.py`（新） | 仓库级校验（spec 7.1） | 3–6 |
| `src/ppt_templates/paths.py`（新） | 点号路径：数据取值、找子 Schema | 4 |
| `src/ppt_templates/components/__init__.py` | 组件注册表改为 `Component(render, schema)` | 4, 8, 9 |
| `src/ppt_templates/catalog.py`（新） | 生成、读取、筛选 `catalog.json` | 6 |
| `src/ppt_templates/cli.py` | 新增 `validate / catalog / list / show` | 6 |
| `src/ppt_templates/draw.py` | 新增 `add_bullets`；`emu_box`、`add_run` 改为公开 | 7 |
| `src/ppt_templates/components/table.py`（新） | 原生表格组件 | 8 |
| `src/ppt_templates/components/block_diagram.py`（新） | 框图组件 | 9 |
| `tests/factories.py`（新） | 测试用模板 | 3, 7–9 |
| `tests/conftest.py` | 新增 `make_repo` 夹具 | 3, 6 |

---

### Task 1: 公共 Schema 模块与 deck Schema

**Files:**
- Create: `src/ppt_templates/schemas.py`
- Create: `schema/deck.schema.json`
- Modify: `src/ppt_templates/slots.py`（整文件替换）
- Modify: `src/ppt_templates/render.py`（删除 `render_deck` 开头的手写结构检查）
- Test: `tests/test_schemas.py`（新）、`tests/test_render.py`（追加一个测试）

**Interfaces:**
- Produces:
  - `schemas.load_schema(root: Path, name: str) -> dict`：读取 `<root>/schema/<name>.schema.json`，结果缓存。
  - `schemas.errors(schema: dict, instance, prefix: tuple = ()) -> list[str]`：每项形如 `"/pages/0/data/title  长度 30，超过上限 14"`，按路径、消息排序；无错返回 `[]`。
  - `schemas.message(e: ValidationError) -> str`、`schemas.pointer(parts) -> str`。
  - `slots.prepare_pages(deck, root)` 行为不变，但先按 `deck.schema.json` 检查结构，结构错误抛 `PptError("deck 结构错误：\n...")`。

- [ ] **Step 1: 写失败的测试**

`tests/test_schemas.py`：

```python
from ppt_templates.schemas import errors, load_schema


def test_errors_are_sorted_pointer_prefixed_and_chinese():
    schema = {
        "type": "object",
        "required": ["a"],
        "additionalProperties": False,
        "properties": {
            "b": {"type": "string", "maxLength": 2},
            "c": {"const": 12},
            "d": {"enum": ["x", "y"]},
        },
    }
    assert errors(schema, {"b": "长长长", "c": 13, "d": "z", "e": 1}, prefix=("pages", 0)) == [
        "/pages/0  不允许的字段 e",
        "/pages/0  缺少必填字段 a",
        "/pages/0/b  长度 3，超过上限 2",
        "/pages/0/c  必须是 12，实际是 13",
        "/pages/0/d  取值 z 不在可选范围 ['x', 'y']",
    ]


def test_root_pointer_is_slash():
    assert errors({"type": "object", "required": ["a"]}, {}) == ["/  缺少必填字段 a"]


def test_deck_schema(root):
    schema = load_schema(root, "deck")
    ok = {"style": "default", "pages": [{"template": "system.solution-layered-arch", "data": {}}]}
    assert errors(schema, ok) == []
    assert errors(schema, {"pages": []}) == ["/pages  共 0 项，低于下限 1"]
    assert errors(schema, {"pages": [{"template": "x", "data": {}, "extra": 1}]}) == [
        "/pages/0  不允许的字段 extra",
        "/pages/0/template  x 不符合格式 ^[a-z]+\\.[a-z0-9]+(-[a-z0-9]+)*$",
    ]
```

在 `tests/test_render.py` 末尾追加：

```python
def test_deck_structure_errors_are_reported(root):
    with pytest.raises(PptError, match="deck 结构错误"):
        render_deck({"pages": []}, root)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_schemas.py tests/test_render.py::test_deck_structure_errors_are_reported -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'ppt_templates.schemas'`

- [ ] **Step 3: 实现 `schemas.py`**

`src/ppt_templates/schemas.py`：

```python
"""schema/*.schema.json 的加载，以及把 JSON Schema 校验错误格式化为中文消息。"""

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError


@cache
def load_schema(root: Path, name: str) -> dict:
    """读取 <root>/schema/<name>.schema.json。"""
    return json.loads((root / "schema" / f"{name}.schema.json").read_text(encoding="utf-8"))


def message(e: ValidationError) -> str:
    v, limit, inst = e.validator, e.validator_value, e.instance
    if v == "maxLength":
        return f"长度 {len(inst)}，超过上限 {limit}"
    if v == "minLength":
        return f"长度 {len(inst)}，低于下限 {limit}"
    if v == "maxItems":
        return f"共 {len(inst)} 项，超过上限 {limit}"
    if v == "minItems":
        return f"共 {len(inst)} 项，低于下限 {limit}"
    if v == "required":
        return "缺少必填字段 " + "、".join(k for k in limit if k not in inst)
    if v == "const":
        return f"必须是 {limit}，实际是 {inst}"
    if v == "enum":
        return f"取值 {inst} 不在可选范围 {limit}"
    if v == "additionalProperties":
        return "不允许的字段 " + "、".join(k for k in inst if k not in e.schema.get("properties", {}))
    if v == "pattern":
        return f"{inst} 不符合格式 {limit}"
    if v == "type":
        return f"类型应为 {limit}"
    if v == "oneOf":
        return "以下写法必须且只能满足一种：" + " / ".join(json.dumps(s, ensure_ascii=False) for s in limit)
    return e.message


def pointer(parts) -> str:
    return "".join("/" + str(p).replace("~", "~0").replace("/", "~1") for p in parts) or "/"


def errors(schema: dict, instance, prefix=()) -> list[str]:
    """「<JSON Pointer>  <中文消息>」列表，按路径、消息排序；没有错误时返回空列表。"""
    found = [(list(e.absolute_path), message(e)) for e in Draft202012Validator(schema).iter_errors(instance)]
    found.sort(key=lambda f: ([str(p) for p in f[0]], f[1]))
    return [f"{pointer([*prefix, *path])}  {msg}" for path, msg in found]
```

- [ ] **Step 4: 写 deck Schema**

`schema/deck.schema.json`：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "deck（统一调用格式）",
  "type": "object",
  "required": ["pages"],
  "additionalProperties": false,
  "properties": {
    "style": {"type": "string", "description": "风格名，对应 styles/<style>/，默认 default"},
    "pages": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["template", "data"],
        "additionalProperties": false,
        "properties": {
          "template": {
            "type": "string",
            "pattern": "^[a-z]+\\.[a-z0-9]+(-[a-z0-9]+)*$",
            "description": "模板 id：<主题>.<目录名>"
          },
          "data": {"type": "object", "description": "按模板 slots 填写的内容"}
        }
      }
    }
  }
}
```

- [ ] **Step 5: 改写 `slots.py`，复用 `schemas.errors`**

整文件替换为：

```python
"""用模板的 slots（JSON Schema）校验页内容，并补全 default。"""

from copy import deepcopy
from pathlib import Path

from .errors import PptError
from .loader import load_template
from .schemas import errors, load_schema


def fill_defaults(schema: dict, value):
    """返回补全了缺失字段 default 的副本，递归处理 object 和 array。"""
    if isinstance(value, dict):
        out = {}
        for key, sub in schema.get("properties", {}).items():
            if key not in value and "default" in sub:
                out[key] = deepcopy(sub["default"])
        for key, item in value.items():
            sub = schema.get("properties", {}).get(key)
            out[key] = fill_defaults(sub, item) if sub else deepcopy(item)
        return out
    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        return [fill_defaults(schema["items"], item) for item in value]
    return deepcopy(value)


def prepare_pages(deck, root: Path) -> list[tuple[dict, dict]]:
    """校验 deck 结构和每页内容，返回 [(template, 补全默认值后的 data)]；有错则汇总后抛 PptError。"""
    structure = errors(load_schema(root, "deck"), deck)
    if structure:
        raise PptError("deck 结构错误：\n" + "\n".join(structure))
    pages, problems = [], []
    for i, page in enumerate(deck["pages"]):
        tid = page["template"]
        where = f"第 {i + 1} 页 {tid}"
        try:
            template = load_template(root, tid)
        except PptError as e:
            problems.append(f"{where}  /pages/{i}/template  {e}")
            continue
        found = errors(template["slots"], page["data"], prefix=("pages", i, "data"))
        problems += [f"{where}  {e}" for e in found]
        if not found:
            pages.append((template, fill_defaults(template["slots"], page["data"])))
    if problems:
        raise PptError("\n".join(problems))
    return pages
```

- [ ] **Step 6: 删除 `render.py` 里的手写结构检查**

在 `src/ppt_templates/render.py` 的 `render_deck` 中删除这两行（结构检查已移到 `prepare_pages`）：

```python
    if not isinstance(deck, dict) or not deck.get("pages"):
        raise PptError("deck 必须是 {style, pages: [...]} 结构，且至少有一页")
```

- [ ] **Step 7: 运行全部测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS（原有测试中的错误信息格式不变）

- [ ] **Step 8: 提交**

```bash
git add src/ppt_templates/schemas.py src/ppt_templates/slots.py src/ppt_templates/render.py schema/deck.schema.json tests/test_schemas.py tests/test_render.py
git commit -m "Add shared schema module and deck schema" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 风格 Schema（字体、token、字号写进 Schema）

**Files:**
- Create: `schema/style.schema.json`
- Modify: `src/ppt_templates/loader.py`（`load_style` 改为按 Schema 校验，删除 `TEXT_SIZES`）
- Modify: `AGENTS.md`（第 34 行引用位置）
- Test: `tests/test_style.py`（新）；从 `tests/test_render.py` 删除 `test_style_constraints_are_enforced`

**Interfaces:**
- Consumes: `schemas.errors`、`schemas.load_schema`（Task 1）
- Produces:
  - `loader.load_style(root, name) -> dict`：不合规时抛 `PptError("风格 <name> 不合规：\n<错误列表>")`。
  - `loader.FONT = "微软雅黑"` 保留（`preview.py` 在用）。
  - `style.schema.json` 中 `properties.colors.required` 和 `properties.text_styles.required` 是颜色 token、文字样式 token 的唯一来源（Task 3、4 读取）。

- [ ] **Step 1: 写失败的测试**

`tests/test_style.py`：

```python
import re
import shutil

import pytest
import yaml

from ppt_templates.errors import PptError
from ppt_templates.loader import load_style


def test_default_style_is_valid(root):
    assert load_style(root, "default")["fonts"] == {"cjk": "微软雅黑", "latin": "微软雅黑"}


@pytest.mark.parametrize("patch, message", [
    (lambda s: s["text_styles"]["body"].update(size=13), "/text_styles/body/size  必须是 12，实际是 13"),
    (lambda s: s["text_styles"]["title"].update(size=18), "/text_styles/title/size  必须是 24，实际是 18"),
    (lambda s: s["text_styles"].update(h3={"size": 14, "color": "text"}), "/text_styles  不允许的字段 h3"),
    (lambda s: s["fonts"].update(latin="Arial"), "/fonts/latin  必须是 微软雅黑，实际是 Arial"),
    (lambda s: s["colors"].update(accent="blue"), "/colors/accent  blue 不符合格式"),
    (lambda s: s["frame"].pop("body"), "/frame  缺少必填字段 body"),
])
def test_style_constraints_are_enforced(root, tmp_path, patch, message):
    shutil.copytree(root / "schema", tmp_path / "schema")
    shutil.copytree(root / "styles", tmp_path / "styles")
    path = tmp_path / "styles" / "default" / "style.yaml"
    style = yaml.safe_load(path.read_text(encoding="utf-8"))
    patch(style)
    path.write_text(yaml.safe_dump(style, allow_unicode=True), encoding="utf-8")
    with pytest.raises(PptError, match=re.escape(message)):
        load_style(tmp_path, "default")
```

从 `tests/test_render.py` 中删除整个 `@pytest.mark.parametrize(...)` 装饰的 `test_style_constraints_are_enforced` 函数（已移到 `tests/test_style.py`）。

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_style.py -v`
Expected: FAIL——字号和字体用例的错误信息仍是旧格式（如 `body 的字号必须是 12，实际是 13`），颜色格式错误和缺少 `frame.body` 的用例根本不抛异常

- [ ] **Step 3: 写风格 Schema**

`schema/style.schema.json`：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "风格（style.yaml）",
  "type": "object",
  "required": ["fonts", "colors", "text_styles", "frame"],
  "additionalProperties": false,
  "properties": {
    "master": {"type": "string"},
    "master_layout": {"type": "string"},
    "fonts": {
      "type": "object",
      "required": ["cjk", "latin"],
      "additionalProperties": false,
      "properties": {
        "cjk": {"const": "微软雅黑"},
        "latin": {"const": "微软雅黑"}
      }
    },
    "colors": {
      "type": "object",
      "required": ["primary", "accent", "text", "muted", "line", "surface", "bg", "on_primary", "highlight", "highlight_strong"],
      "additionalProperties": false,
      "properties": {
        "primary": {"$ref": "#/$defs/hex"},
        "accent": {"$ref": "#/$defs/hex"},
        "text": {"$ref": "#/$defs/hex"},
        "muted": {"$ref": "#/$defs/hex"},
        "line": {"$ref": "#/$defs/hex"},
        "surface": {"$ref": "#/$defs/hex"},
        "bg": {"$ref": "#/$defs/hex"},
        "on_primary": {"$ref": "#/$defs/hex"},
        "highlight": {"$ref": "#/$defs/hex"},
        "highlight_strong": {"$ref": "#/$defs/hex"}
      }
    },
    "text_styles": {
      "type": "object",
      "required": ["title", "title_suffix", "subtitle", "emphasis", "body", "body_strong", "detail", "caption", "footnote", "kpi"],
      "additionalProperties": false,
      "properties": {
        "title": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 24}}},
        "title_suffix": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 18}}},
        "subtitle": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 18}}},
        "emphasis": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 14}}},
        "body": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 12}}},
        "body_strong": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 12}}},
        "detail": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 10}}},
        "caption": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 9}}},
        "footnote": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 8}}},
        "kpi": {"$ref": "#/$defs/text_style", "properties": {"size": {"const": 24}}}
      }
    },
    "frame": {
      "type": "object",
      "required": ["title", "takeaway", "body"],
      "additionalProperties": false,
      "properties": {
        "title": {"$ref": "#/$defs/region"},
        "takeaway": {"$ref": "#/$defs/region"},
        "body": {
          "type": "object",
          "required": ["box"],
          "additionalProperties": false,
          "properties": {"box": {"$ref": "#/$defs/box"}}
        },
        "decorations": {"type": "array", "items": {"$ref": "#/$defs/decoration"}}
      }
    }
  },
  "$defs": {
    "hex": {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
    "box": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "number"}},
    "text_style": {
      "type": "object",
      "required": ["size", "color"],
      "additionalProperties": false,
      "properties": {
        "size": {"type": "number"},
        "bold": {"type": "boolean"},
        "color": {"type": "string"}
      }
    },
    "region": {
      "type": "object",
      "required": ["box", "style"],
      "additionalProperties": false,
      "properties": {
        "box": {"$ref": "#/$defs/box"},
        "style": {"type": "string"},
        "suffix_style": {"type": "string"},
        "align": {"enum": ["left", "center", "right"]},
        "valign": {"enum": ["top", "middle", "bottom"]}
      }
    },
    "decoration": {
      "type": "object",
      "required": ["type", "box", "fill"],
      "additionalProperties": false,
      "properties": {
        "type": {"const": "shape"},
        "box": {"$ref": "#/$defs/box"},
        "fill": {"type": "string"},
        "line": {"type": "string"},
        "shape": {"enum": ["rect", "rounded"]}
      }
    }
  }
}
```

- [ ] **Step 4: `load_style` 改为按 Schema 校验**

在 `src/ppt_templates/loader.py` 中：

1. 在 `from .errors import PptError` 下面加一行：

```python
from .schemas import errors, load_schema
```

2. 把 `FONT = "微软雅黑"` 之后到文件中 `load_style` 函数结束的整段（含 `TEXT_SIZES` 字典和旧的 `load_style`）替换为：

```python
FONT = "微软雅黑"


def load_style(root: Path, name: str) -> dict:
    """读取风格，并按 schema/style.schema.json 检查：字体固定微软雅黑，文字样式与字号固定。"""
    style = load_yaml(root / "styles" / name / "style.yaml")
    problems = errors(load_schema(root, "style"), style)
    if problems:
        raise PptError(f"风格 {name} 不合规：\n" + "\n".join(problems))
    return style
```

- [ ] **Step 5: 更新 AGENTS.md 中的引用位置**

把 `AGENTS.md` 中的

```
每个文字样式 token 的字号固定在 `src/ppt_templates/loader.py` 的 `TEXT_SIZES` 里，风格不能改，加载风格时检查；
```

改为

```
每个文字样式 token 的字号固定在 `schema/style.schema.json` 里，风格不能改，加载风格时检查；
```

- [ ] **Step 6: 运行全部测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add schema/style.schema.json src/ppt_templates/loader.py tests/test_style.py tests/test_render.py AGENTS.md
git commit -m "Validate styles against style.schema.json" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: taxonomy、模板 Schema 与仓库校验骨架

**Files:**
- Create: `src/ppt_templates/taxonomy.py`
- Create: `schema/template.schema.json`
- Create: `src/ppt_templates/validate.py`
- Create: `tests/factories.py`
- Modify: `tests/conftest.py`（新增 `make_repo` 夹具）
- Test: `tests/test_validate.py`（新）、`tests/test_repo.py`（新）

**Interfaces:**
- Consumes: `schemas.errors`、`schemas.load_schema`、`loader.load_yaml`
- Produces:
  - `taxonomy.Taxonomy(topics: dict[str, dict], roles: dict[str, dict])`
  - `taxonomy.check_taxonomy(raw: dict) -> list[str]`
  - `taxonomy.load_taxonomy(root) -> Taxonomy`（有错抛 `PptError`）
  - `validate.Report(errors: list[str], warnings: list[str])`
  - `validate.style_tokens(root) -> tuple[set[str], set[str]]`：（颜色 token，文字样式 token）
  - `validate.check_meta(f: str, topic: str, name: str, tpl: dict, tax: Taxonomy) -> list[str]`
  - `validate.validate_repo(root) -> Report`
  - 测试夹具 `make_repo(templates: dict[str, tuple[dict, dict | None]]) -> Path`；工厂 `factories.mini_template(**overrides) -> tuple[dict, dict]`（id 为 `common.summary-note`）

- [ ] **Step 1: 写测试工厂和夹具**

`tests/factories.py`：

```python
"""测试用的模板。每个函数返回 (template, example)。"""


def deck_of(template_id: str, data: dict) -> dict:
    return {"style": "default", "pages": [{"template": template_id, "data": data}]}


def mini_template(**overrides):
    """common.summary-note：一句话总结页；overrides 覆盖 template 顶层字段。"""
    template = {
        "id": "common.summary-note",
        "name": "一句话总结",
        "roles": ["summary"],
        "when_to_use": "用一句话总结全文",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "note"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "note": {"type": "string", "maxLength": 60},
            },
        },
        "layout": [{"type": "text", "box": [0, 0, 1216, 80], "bind": "note", "style": "emphasis"}],
    }
    template.update(overrides)
    return template, {"title": "总结", "note": "一句话说清楚结论"}
```

`tests/conftest.py` 整文件替换为：

```python
import shutil
from pathlib import Path

import pytest
import yaml

from ppt_templates.loader import find_repo_root, load_example

TEMPLATE_ID = "system.solution-layered-arch"


@pytest.fixture(scope="session")
def root():
    return find_repo_root()


@pytest.fixture
def deck(root):
    return {"style": "default", "pages": [{"template": TEMPLATE_ID, "data": load_example(root, TEMPLATE_ID)}]}


def _dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


@pytest.fixture
def make_repo(root, tmp_path):
    """在临时目录搭一个最小仓库：复制 taxonomy / schema / styles，再写入给定的模板。"""

    def make(templates: dict) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        shutil.copy(root / "taxonomy.yaml", repo / "taxonomy.yaml")
        shutil.copytree(root / "schema", repo / "schema")
        shutil.copytree(root / "styles", repo / "styles")
        for tid, (template, example) in templates.items():
            topic, name = tid.split(".", 1)
            d = repo / "templates" / topic / name
            d.mkdir(parents=True)
            _dump(d / "template.yaml", template)
            if example is not None:
                _dump(d / "example.yaml", example)
        return repo

    return make
```

- [ ] **Step 2: 写失败的测试**

`tests/test_repo.py`：

```python
"""对仓库里真实的模板做整体检查。"""

from ppt_templates.validate import validate_repo


def test_repository_is_valid(root):
    assert validate_repo(root).errors == []
```

`tests/test_validate.py`：

```python
import pytest

from factories import mini_template
from ppt_templates.taxonomy import check_taxonomy
from ppt_templates.validate import validate_repo

F = "templates/common/summary-note/template.yaml"


def test_taxonomy_ids_must_be_single_lowercase_words_and_unique():
    raw = {
        "topics": [{"id": "system", "name": "系统"}, {"id": "system", "name": "重复"}],
        "roles": [{"id": "next-steps", "name": "下一步"}],
    }
    assert check_taxonomy(raw) == [
        "taxonomy.yaml  /topics/1/id  重复的 id system",
        "taxonomy.yaml  /roles/0/id  'next-steps' 必须是单个小写英文单词",
    ]


def test_mini_template_is_valid(make_repo):
    repo = make_repo({"common.summary-note": mini_template()})
    assert validate_repo(repo).errors == []


@pytest.mark.parametrize("overrides, expected", [
    ({"id": "common.other"}, "/id  应为 common.summary-note（由目录决定），实际是 common.other"),
    ({"roles": ["nope"]}, "/roles/0  页功能 nope 不在 taxonomy.yaml 中"),
    ({"roles": ["risk"]}, "/roles/0  目录名 summary-note 必须以主页功能 risk- 开头"),
    ({"density": "read"}, "/density  目录名以 -read 结尾，当且仅当 density: read"),
    ({"also_fits": ["common"]}, "/also_fits/0  不能包含模板自己的主题"),
    ({"also_fits": ["galaxy"]}, "/also_fits/0  主题 galaxy 不在 taxonomy.yaml 中"),
    ({"level": "module"}, "/level  level 只用于 hardware、software、system 主题"),
    ({"layout": [{"type": "text", "box": [0, 0, 10, 10], "bind": "note", "style": "body", "size": 13}]},
     "/layout/0  不允许的字段 size"),
    ({"frame": "wide"}, "/frame  取值 wide 不在可选范围 ['standard', 'none']"),
])
def test_template_metadata_rules(make_repo, overrides, expected):
    repo = make_repo({"common.summary-note": mini_template(**overrides)})
    assert f"{F}  {expected}" in validate_repo(repo).errors


def test_unknown_topic_directory(make_repo):
    repo = make_repo({"galaxy.summary-note": mini_template(id="galaxy.summary-note")})
    assert "templates/galaxy/summary-note/template.yaml  /  主题目录 galaxy 不在 taxonomy.yaml 中" in validate_repo(repo).errors


def test_slots_must_be_an_object_schema(make_repo):
    repo = make_repo({"common.summary-note": mini_template(slots={"type": "array"})})
    assert f"{F}  /slots/type  顶层必须是 type: object" in validate_repo(repo).errors


def test_missing_example_is_an_error_and_missing_preview_a_warning(make_repo):
    template, _ = mini_template()
    repo = make_repo({"common.summary-note": (template, None)})
    report = validate_repo(repo)
    assert "templates/common/summary-note  缺少 example.yaml" in report.errors
    assert report.warnings == ["templates/common/summary-note  缺少 preview.png（运行 uv run ppt preview common.summary-note --write）"]
```

- [ ] **Step 3: 运行测试，确认失败**

Run: `uv run pytest tests/test_validate.py tests/test_repo.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'ppt_templates.taxonomy'`

- [ ] **Step 4: 实现 `taxonomy.py`**

`src/ppt_templates/taxonomy.py`：

```python
"""taxonomy.yaml：主题与页功能的受控词表。"""

import re
from dataclasses import dataclass
from pathlib import Path

from .errors import PptError
from .loader import load_yaml

ID = re.compile(r"^[a-z]+$")


@dataclass(frozen=True)
class Taxonomy:
    topics: dict[str, dict]  # id → 条目（name / includes / excludes）
    roles: dict[str, dict]   # id → 条目（name / question）


def check_taxonomy(raw: dict) -> list[str]:
    """id 必须是单个小写英文单词且不重复，每个条目都要有 name。"""
    errs = []
    for kind in ("topics", "roles"):
        seen = set()
        for i, entry in enumerate(raw.get(kind) or []):
            tid = entry.get("id")
            if not isinstance(tid, str) or not ID.match(tid):
                errs.append(f"taxonomy.yaml  /{kind}/{i}/id  {tid!r} 必须是单个小写英文单词")
            elif tid in seen:
                errs.append(f"taxonomy.yaml  /{kind}/{i}/id  重复的 id {tid}")
            seen.add(tid)
            if not entry.get("name"):
                errs.append(f"taxonomy.yaml  /{kind}/{i}/name  缺少名称")
        if not raw.get(kind):
            errs.append(f"taxonomy.yaml  /{kind}  不能为空")
    return errs


def load_taxonomy(root: Path) -> Taxonomy:
    raw = load_yaml(root / "taxonomy.yaml")
    errs = check_taxonomy(raw)
    if errs:
        raise PptError("\n".join(errs))
    return Taxonomy({t["id"]: t for t in raw["topics"]}, {r["id"]: r for r in raw["roles"]})
```

- [ ] **Step 5: 写模板 Schema**

`schema/template.schema.json`：

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "页模板（template.yaml）",
  "type": "object",
  "required": ["id", "name", "roles", "when_to_use", "frame", "slots", "layout"],
  "additionalProperties": false,
  "properties": {
    "id": {"type": "string", "pattern": "^[a-z]+\\.[a-z0-9]+(-[a-z0-9]+)*$"},
    "name": {"type": "string", "minLength": 1},
    "roles": {"type": "array", "minItems": 1, "uniqueItems": true, "items": {"type": "string"}},
    "also_fits": {"type": "array", "uniqueItems": true, "items": {"type": "string"}},
    "density": {"enum": ["talk", "read"]},
    "level": {"enum": ["system", "subsystem", "module"]},
    "tags": {"type": "array", "items": {"type": "string"}},
    "when_to_use": {"type": "string", "minLength": 1},
    "when_not_to_use": {"type": "string"},
    "frame": {"enum": ["standard", "none"]},
    "slots": {"type": "object"},
    "layout": {"$ref": "#/$defs/elements"},
    "guidance": {"type": "array", "items": {"type": "string"}}
  },
  "$defs": {
    "length": {
      "oneOf": [
        {"type": "number"},
        {"type": "string", "pattern": "^\\s*-?\\d+(\\.\\d+)?%\\s*([+-]\\s*\\d+(\\.\\d+)?)?\\s*$"}
      ]
    },
    "box": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"$ref": "#/$defs/length"}},
    "elements": {"type": "array", "items": {"$ref": "#/$defs/element"}},
    "element": {
      "type": "object",
      "required": ["type"],
      "properties": {"type": {"enum": ["text", "bullets", "shape", "grid", "component"]}},
      "allOf": [
        {"if": {"properties": {"type": {"const": "text"}}}, "then": {"$ref": "#/$defs/text"}},
        {"if": {"properties": {"type": {"const": "bullets"}}}, "then": {"$ref": "#/$defs/bullets"}},
        {"if": {"properties": {"type": {"const": "shape"}}}, "then": {"$ref": "#/$defs/shape"}},
        {"if": {"properties": {"type": {"const": "grid"}}}, "then": {"$ref": "#/$defs/grid"}},
        {"if": {"properties": {"type": {"const": "component"}}}, "then": {"$ref": "#/$defs/component"}}
      ]
    },
    "text": {
      "required": ["box", "style"],
      "oneOf": [{"required": ["bind"]}, {"required": ["value"]}],
      "additionalProperties": false,
      "properties": {
        "type": {},
        "box": {"$ref": "#/$defs/box"},
        "bind": {"type": "string"},
        "value": {"type": "string"},
        "style": {"type": "string"},
        "color": {"type": "string"},
        "align": {"enum": ["left", "center", "right"]},
        "valign": {"enum": ["top", "middle", "bottom"]}
      }
    },
    "bullets": {
      "required": ["box", "bind", "style"],
      "additionalProperties": false,
      "properties": {
        "type": {},
        "box": {"$ref": "#/$defs/box"},
        "bind": {"type": "string"},
        "style": {"type": "string"},
        "color": {"type": "string"}
      }
    },
    "shape": {
      "required": ["box", "fill"],
      "additionalProperties": false,
      "properties": {
        "type": {},
        "box": {"$ref": "#/$defs/box"},
        "fill": {"type": "string"},
        "line": {"type": "string"},
        "shape": {"enum": ["rect", "rounded"]}
      }
    },
    "grid": {
      "required": ["box", "bind", "columns", "item"],
      "additionalProperties": false,
      "properties": {
        "type": {},
        "box": {"$ref": "#/$defs/box"},
        "bind": {"type": "string"},
        "columns": {"type": "integer", "minimum": 1},
        "gap": {"type": "number", "minimum": 0},
        "item": {"$ref": "#/$defs/elements"}
      }
    },
    "component": {
      "required": ["box", "component", "bind"],
      "additionalProperties": false,
      "properties": {
        "type": {},
        "box": {"$ref": "#/$defs/box"},
        "component": {"type": "string"},
        "bind": {"type": "string"},
        "props": {"type": "object"}
      }
    }
  }
}
```

- [ ] **Step 6: 实现 `validate.py` 骨架**

`src/ppt_templates/validate.py`：

```python
"""仓库级校验（spec 7.1）：taxonomy、风格、每个模板。"""

from dataclasses import dataclass, field
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .errors import PptError
from .loader import load_yaml
from .schemas import errors as schema_errors
from .schemas import load_schema
from .taxonomy import Taxonomy, load_taxonomy

LEVEL_TOPICS = {"system", "hardware", "software"}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def style_tokens(root: Path) -> tuple[set[str], set[str]]:
    """(颜色 token, 文字样式 token)：取自 style.schema.json 的 required 列表。"""
    props = load_schema(root, "style")["properties"]
    return set(props["colors"]["required"]), set(props["text_styles"]["required"])


def check_style_refs(rel: str, style: dict, colors: set[str], texts: set[str]) -> list[str]:
    """风格内部引用的 token 都要存在：文字样式的颜色、页框区域的文字样式、装饰的颜色。"""
    errs = []
    for token, ts in style["text_styles"].items():
        if ts["color"] not in colors:
            errs.append(f"{rel}  /text_styles/{token}/color  未知颜色 token {ts['color']}")
    for region in ("title", "takeaway"):
        for key in ("style", "suffix_style"):
            value = style["frame"][region].get(key)
            if value is not None and value not in texts:
                errs.append(f"{rel}  /frame/{region}/{key}  未知文字样式 token {value}")
    for i, deco in enumerate(style["frame"].get("decorations", [])):
        for key in ("fill", "line"):
            if key in deco and deco[key] not in colors:
                errs.append(f"{rel}  /frame/decorations/{i}/{key}  未知颜色 token {deco[key]}")
    return errs


def check_meta(f: str, topic: str, name: str, tpl: dict, tax: Taxonomy) -> list[str]:
    """spec 7.1 第 3 条：id 与路径、主题、页功能、目录名前缀、-read 后缀、also_fits、level。"""
    errs = []

    def err(ptr, msg):
        errs.append(f"{f}  {ptr}  {msg}")

    if tpl["id"] != f"{topic}.{name}":
        err("/id", f"应为 {topic}.{name}（由目录决定），实际是 {tpl['id']}")
    if topic not in tax.topics:
        err("/", f"主题目录 {topic} 不在 taxonomy.yaml 中")
    for i, role in enumerate(tpl["roles"]):
        if role not in tax.roles:
            err(f"/roles/{i}", f"页功能 {role} 不在 taxonomy.yaml 中")
    if not name.startswith(tpl["roles"][0] + "-"):
        err("/roles/0", f"目录名 {name} 必须以主页功能 {tpl['roles'][0]}- 开头")
    if name.endswith("-read") != (tpl.get("density", "talk") == "read"):
        err("/density", "目录名以 -read 结尾，当且仅当 density: read")
    for i, other in enumerate(tpl.get("also_fits", [])):
        if other not in tax.topics:
            err(f"/also_fits/{i}", f"主题 {other} 不在 taxonomy.yaml 中")
        elif other == topic:
            err(f"/also_fits/{i}", "不能包含模板自己的主题")
    if "level" in tpl and topic not in LEVEL_TOPICS:
        err("/level", f"level 只用于 {'、'.join(sorted(LEVEL_TOPICS))} 主题")
    return errs


def _template_dirs(root: Path) -> list[Path]:
    return sorted(p for p in (root / "templates").glob("*/*") if p.is_dir() and not p.name.startswith("."))


def validate_repo(root: Path) -> Report:
    report = Report()
    try:
        tax = load_taxonomy(root)
    except PptError as e:
        report.errors += str(e).splitlines()
        return report

    colors, texts = style_tokens(root)
    style_schema = load_schema(root, "style")
    for sdir in sorted(p for p in (root / "styles").iterdir() if p.is_dir()):
        rel = f"styles/{sdir.name}/style.yaml"
        style = load_yaml(sdir / "style.yaml")
        problems = [f"{rel}  {e}" for e in schema_errors(style_schema, style)]
        report.errors += problems or check_style_refs(rel, style, colors, texts)

    template_schema = load_schema(root, "template")
    for tdir in _template_dirs(root):
        topic, name = tdir.parent.name, tdir.name
        rel = f"templates/{topic}/{name}"
        f = f"{rel}/template.yaml"
        if not (tdir / "template.yaml").is_file():
            report.errors.append(f"{rel}  缺少 template.yaml")
            continue
        tpl = load_yaml(tdir / "template.yaml")
        problems = [f"{f}  {e}" for e in schema_errors(template_schema, tpl)]
        if not problems:
            try:
                Draft202012Validator.check_schema(tpl["slots"])
            except SchemaError as e:
                problems.append(f"{f}  /slots  不是合法的 JSON Schema：{e.message}")
        if not problems and tpl["slots"].get("type") != "object":
            problems.append(f"{f}  /slots/type  顶层必须是 type: object")
        if problems:
            report.errors += problems
            continue
        report.errors += check_meta(f, topic, name, tpl, tax)
        if not (tdir / "example.yaml").is_file():
            report.errors.append(f"{rel}  缺少 example.yaml")
        if not (tdir / "preview.png").is_file():
            report.warnings.append(f"{rel}  缺少 preview.png（运行 uv run ppt preview {topic}.{name} --write）")
    return report
```

- [ ] **Step 7: 运行测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 8: 提交**

```bash
git add src/ppt_templates/taxonomy.py src/ppt_templates/validate.py schema/template.schema.json tests/factories.py tests/conftest.py tests/test_validate.py tests/test_repo.py
git commit -m "Add taxonomy check, template schema and repo validator skeleton" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 绑定与 token 校验（组件注册表带 Schema）

**Files:**
- Create: `src/ppt_templates/paths.py`
- Modify: `src/ppt_templates/components/__init__.py`（整文件替换）
- Modify: `src/ppt_templates/components/layered_arch.py`（新增 `SCHEMA`）
- Modify: `src/ppt_templates/render.py`（改用 `paths.lookup` 和 `Component.render`）
- Modify: `src/ppt_templates/validate.py`（新增 `check_layout` 并在 `validate_repo` 中调用）
- Test: `tests/test_paths.py`（新）、`tests/test_validate.py`（追加）

**Interfaces:**
- Consumes: `validate.validate_repo`、`factories.mini_template`、`make_repo`（Task 3）
- Produces:
  - `paths.lookup(scope, path: str)`：数据取值，`"."` 返回 scope 本身，不存在返回 `None`。
  - `paths.slot_at(schema: dict, path: str) -> dict | None`：子 Schema。
  - `components.Component(render: Callable, schema: dict)`；`components.COMPONENTS: dict[str, Component]`。
  - `layered_arch.SCHEMA: dict`
  - `validate.FRAME_SLOTS = ("title", "title_suffix", "takeaway")`
  - `validate.check_layout(f: str, tpl: dict, colors: set[str], texts: set[str]) -> list[str]`

- [ ] **Step 1: 写失败的测试**

`tests/test_paths.py`：

```python
from ppt_templates.paths import lookup, slot_at


def test_slot_at():
    schema = {"type": "object", "properties": {"a": {"type": "object", "properties": {"b": {"type": "string"}}}}}
    assert slot_at(schema, "a.b") == {"type": "string"}
    assert slot_at(schema, ".") is schema
    assert slot_at(schema, "a.c") is None
    assert slot_at(schema, "x.y") is None


def test_lookup():
    assert lookup({"a": {"b": "x"}}, "a.b") == "x"
    assert lookup({"a": {}}, "a.b") is None
    assert lookup("item", ".") == "item"
```

在 `tests/test_validate.py` 末尾追加：

```python
def _errors(make_repo, **overrides):
    repo = make_repo({"common.summary-note": mini_template(**overrides)})
    return [e.removeprefix(f"{F}  ") for e in validate_repo(repo).errors if e.startswith(F)]


def _slots(**extra):
    props = {"title": {"type": "string", "maxLength": 14}, "note": {"type": "string", "maxLength": 60}, **extra}
    return {"type": "object", "required": ["title"], "properties": props}


NOTE = {"type": "text", "box": [0, 0, 600, 80], "bind": "note", "style": "body"}


def test_unbound_slot(make_repo):
    assert "/slots/properties/extra  槽位没有被 layout 渲染" in _errors(
        make_repo, slots=_slots(extra={"type": "string"}))


def test_bind_to_missing_slot(make_repo):
    assert "/layout/1/bind  槽位 nope 不存在" in _errors(
        make_repo, layout=[NOTE, {**NOTE, "bind": "nope"}])


def test_layout_cannot_bind_frame_slots(make_repo):
    assert "/layout/1/bind  title 由页框渲染，layout 不能再绑定" in _errors(
        make_repo, layout=[NOTE, {**NOTE, "bind": "title"}])


def test_standard_frame_requires_title(make_repo):
    slots = _slots()
    slots["required"] = ["note"]
    assert "/slots/required  frame: standard 的模板必须把 title 列为必填" in _errors(make_repo, slots=slots)


def test_frame_slots_must_be_strings(make_repo):
    assert "/slots/properties/takeaway  页框槽位必须是 type: string" in _errors(
        make_repo, slots=_slots(takeaway={"type": "array"}))


def test_unknown_tokens(make_repo):
    errs = _errors(make_repo, layout=[{**NOTE, "style": "h3", "color": "red"},
                                      {"type": "shape", "box": [0, 100, 10, 10], "fill": "blue"}])
    assert "/layout/0/style  未知文字样式 token h3" in errs
    assert "/layout/0/color  未知颜色 token red" in errs
    assert "/layout/1/fill  未知颜色 token blue" in errs


def test_duplicate_binding(make_repo):
    assert "/layout/1/bind  槽位 note 被重复绑定" in _errors(make_repo, layout=[NOTE, NOTE])


def test_bind_type_must_match_element(make_repo):
    slots = _slots(items={"type": "array", "items": {"type": "string"}})
    errs = _errors(make_repo, slots=slots, layout=[
        NOTE,
        {"type": "text", "box": [0, 100, 600, 80], "bind": "items", "style": "body"},
        {"type": "grid", "box": [0, 200, 600, 80], "bind": "items", "columns": 2, "item": []},
    ])
    assert "/layout/1/bind  text 只能绑定 string 槽位，实际是 array" in errs
    assert "/layout/2/bind  grid 绑定的数组必须声明 maxItems" in errs


def test_unknown_component(make_repo):
    assert "/layout/1/component  未知组件 pie" in _errors(
        make_repo, layout=[NOTE, {"type": "component", "component": "pie", "box": [0, 100, 10, 10], "bind": "note"}])


def test_component_slot_type_must_match(make_repo):
    errs = _errors(make_repo, layout=[
        NOTE, {"type": "component", "component": "layered-arch", "box": [0, 100, 600, 300], "bind": "title"}])
    assert "/layout/1/bind  组件 layered-arch 需要 array 类型的槽位，实际是 string" in errs


def test_frame_none_renders_title_through_layout(make_repo):
    layout = [{"type": "text", "box": [32, 32, 1216, 40], "bind": "title", "style": "title"},
              {"type": "text", "box": [32, 100, 1216, 80], "bind": "note", "style": "body"}]
    assert _errors(make_repo, frame="none", layout=layout) == []
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_paths.py tests/test_validate.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'ppt_templates.paths'`，以及新增的绑定测试断言失败

- [ ] **Step 3: 实现 `paths.py`**

`src/ppt_templates/paths.py`：

```python
"""点号路径：在数据里取值（lookup），在 JSON Schema 里找对应的子 schema（slot_at）。"""


def lookup(scope, path: str):
    """相对 scope 解析点号路径；"." 是 scope 本身；路径不存在（可选槽位未填）返回 None。"""
    if path == ".":
        return scope
    for key in path.split("."):
        if not isinstance(scope, dict) or key not in scope:
            return None
        scope = scope[key]
    return scope


def slot_at(schema: dict, path: str) -> dict | None:
    """点号路径在 object schema 里对应的子 schema；"." 是 schema 本身；不存在返回 None。"""
    if path == ".":
        return schema
    for key in path.split("."):
        if not isinstance(schema, dict):
            return None
        schema = (schema.get("properties") or {}).get(key)
        if schema is None:
            return None
    return schema
```

- [ ] **Step 4: 组件注册表带上数据 Schema**

`src/ppt_templates/components/__init__.py` 整文件替换为：

```python
"""内置组件注册表：组件名 → Component(render, schema)。"""

from collections.abc import Callable
from dataclasses import dataclass

from . import layered_arch


@dataclass(frozen=True)
class Component:
    render: Callable  # render(slide, style, box, data, props)
    schema: dict      # 组件接受的数据（JSON Schema）；校验器用它检查模板的 example


COMPONENTS = {
    "layered-arch": Component(layered_arch.render, layered_arch.SCHEMA),
}
```

在 `src/ppt_templates/components/layered_arch.py` 的常量定义（`LEGEND_H, SWATCH, SWATCH_GAP = 28, 14, 6`）下方加入：

```python

SCHEMA = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "required": ["name", "modules"],
        "properties": {
            "name": {"type": "string"},
            "modules": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {"name": {"type": "string"}, "highlight": {"type": "boolean"}},
                },
            },
        },
    },
}
```

- [ ] **Step 5: `render.py` 改用 `paths.lookup` 和 `Component.render`**

在 `src/ppt_templates/render.py` 中：

1. 删除整个 `_lookup` 函数定义。
2. 在 import 区加入 `from .paths import lookup`。
3. 把文件中所有 `_lookup(` 替换为 `lookup(`。
4. 把
```python
                COMPONENTS[el["component"]](slide, style, tf(ref_box), data, el.get("props", {}))
```
替换为
```python
                COMPONENTS[el["component"]].render(slide, style, tf(ref_box), data, el.get("props", {}))
```

- [ ] **Step 6: 在 `validate.py` 中实现 `check_layout`**

在 `src/ppt_templates/validate.py` 的 import 区加入：

```python
from .components import COMPONENTS
from .paths import slot_at
```

在 `LEVEL_TOPICS = ...` 下一行加入：

```python
FRAME_SLOTS = ("title", "title_suffix", "takeaway")
```

在 `check_meta` 函数之后加入：

```python
def _type_error(el: dict, slot: dict) -> str | None:
    """bind 的槽位类型是否符合元素要求（spec 4.3 表格）；符合返回 None。"""
    kind, t = el["type"], slot.get("type")
    if kind == "text":
        return None if t == "string" else f"text 只能绑定 string 槽位，实际是 {t}"
    if kind == "bullets":
        items = slot.get("items") or {}
        text_ok = (items.get("properties") or {}).get("text", {}).get("type") == "string"
        if t == "array" and (items.get("type") == "string" or (items.get("type") == "object" and text_ok)):
            return None
        return "bullets 只能绑定 string 数组，或含 string 字段 text 的对象数组"
    if kind == "grid":
        if t != "array":
            return f"grid 只能绑定数组槽位，实际是 {t}"
        return None if "maxItems" in slot else "grid 绑定的数组必须声明 maxItems"
    want = COMPONENTS[el["component"]].schema.get("type")
    return None if t == want else f"组件 {el['component']} 需要 {want} 类型的槽位，实际是 {t}"


def check_layout(f: str, tpl: dict, colors: set[str], texts: set[str]) -> list[str]:
    """spec 7.1 第 5、7 条：槽位都被渲染、bind 存在且类型匹配、页框槽位规则、只引用风格 token。"""
    errs = []
    slots, standard = tpl["slots"], tpl["frame"] == "standard"
    props = slots.get("properties") or {}

    def err(ptr, msg):
        errs.append(f"{f}  {ptr}  {msg}")

    if standard:
        if "title" not in slots.get("required", []):
            err("/slots/required", "frame: standard 的模板必须把 title 列为必填")
        for name in FRAME_SLOTS:
            if name in props and props[name].get("type") != "string":
                err(f"/slots/properties/{name}", "页框槽位必须是 type: string")

    top_paths = set()

    def walk(elements, scope, ptr, top):
        for i, el in enumerate(elements):
            p = f"{ptr}/{i}"
            for key in ("fill", "line", "color"):
                if key in el and el[key] not in colors:
                    err(f"{p}/{key}", f"未知颜色 token {el[key]}")
            if "style" in el and el["style"] not in texts:
                err(f"{p}/style", f"未知文字样式 token {el['style']}")
            if el["type"] == "component" and el["component"] not in COMPONENTS:
                err(f"{p}/component", f"未知组件 {el['component']}")
                continue
            if "bind" not in el:
                continue
            path = el["bind"]
            slot = slot_at(scope, path)
            if slot is None:
                err(f"{p}/bind", f"槽位 {path} 不存在")
                continue
            if top:
                head = path.split(".")[0]
                if path in top_paths:
                    err(f"{p}/bind", f"槽位 {path} 被重复绑定")
                top_paths.add(path)
                if standard and head in FRAME_SLOTS:
                    err(f"{p}/bind", f"{head} 由页框渲染，layout 不能再绑定")
            problem = _type_error(el, slot)
            if problem:
                err(f"{p}/bind", problem)
            elif el["type"] == "grid":
                walk(el["item"], slot.get("items") or {}, f"{p}/item", False)

    walk(tpl["layout"], slots, "/layout", True)
    rendered = {path.split(".")[0] for path in top_paths}
    for name in props:
        if not (standard and name in FRAME_SLOTS) and name not in rendered:
            err(f"/slots/properties/{name}", "槽位没有被 layout 渲染")
    return errs
```

在 `validate_repo` 中，紧接 `report.errors += check_meta(f, topic, name, tpl, tax)` 之后加入一行：

```python
        report.errors += check_layout(f, tpl, colors, texts)
```

- [ ] **Step 7: 运行全部测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS（包括 `tests/test_repo.py::test_repository_is_valid`，真实模板满足所有绑定规则）

- [ ] **Step 8: 提交**

```bash
git add src/ppt_templates/paths.py src/ppt_templates/components src/ppt_templates/render.py src/ppt_templates/validate.py tests/test_paths.py tests/test_validate.py
git commit -m "Validate slot bindings, frame slots and style tokens" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 几何与示例内容校验

**Files:**
- Modify: `src/ppt_templates/validate.py`（新增 `check_geometry`、`check_example` 并接入）
- Test: `tests/test_validate.py`（追加）

**Interfaces:**
- Consumes: `paths.lookup`、`paths.slot_at`、`components.COMPONENTS`（Task 4）
- Produces:
  - `validate.check_geometry(f: str, tpl: dict) -> list[str]`
  - `validate.check_example(rel: str, tpl: dict, example) -> list[str]`（`rel` 形如 `templates/common/summary-note`）

- [ ] **Step 1: 写失败的测试**

在 `tests/test_validate.py` 末尾追加：

```python
def test_element_outside_body_area(make_repo):
    assert "/layout/0/box  超出 body 区 1216×560" in _errors(
        make_repo, layout=[{**NOTE, "box": [0, 0, 1300, 80]}])


def test_grid_item_must_fit_smallest_cell(make_repo):
    slots = _slots(points={"type": "array", "maxItems": 6, "items": {"type": "string"}})
    grid = {"type": "grid", "box": [0, 100, 600, 100], "bind": "points", "columns": 3, "gap": 10,
            "item": [{"type": "text", "box": [0, 0, "100%", 60], "bind": ".", "style": "body"}]}
    assert "/layout/1/item/0/box  按 maxItems=6 计算的单元格 193×45 放不下" in _errors(
        make_repo, slots=slots, layout=[NOTE, grid])


def test_example_must_pass_slots(make_repo):
    template, example = mini_template()
    example["note"] = "长" * 61
    repo = make_repo({"common.summary-note": (template, example)})
    assert "templates/common/summary-note/example.yaml  /note  长度 61，超过上限 60" in validate_repo(repo).errors


def test_component_data_in_example_must_pass_component_schema(make_repo):
    slots = _slots(layers={"type": "array", "items": {"type": "object"}})
    layout = [NOTE, {"type": "component", "component": "layered-arch", "box": [0, 100, 800, 400], "bind": "layers"}]
    template, example = mini_template(slots=slots, layout=layout)
    example["layers"] = [{"name": "接入层"}]
    repo = make_repo({"common.summary-note": (template, example)})
    assert ("templates/common/summary-note/example.yaml  /layers/0  缺少必填字段 modules（组件 layered-arch）"
            in validate_repo(repo).errors)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_validate.py -v`
Expected: 新增的 4 个测试 FAIL（断言的错误信息不存在）

- [ ] **Step 3: 实现 `check_geometry` 和 `check_example`**

在 `src/ppt_templates/validate.py` 的 import 区加入：

```python
import math

from .geometry import CANVAS_H, CANVAS_W, REF_H, REF_W, resolve_box
from .paths import lookup
```

（`import math` 放在标准库 import 一组；`from .paths import slot_at` 改为 `from .paths import lookup, slot_at`，不要重复导入。）

在 `FRAME_SLOTS = ...` 下一行加入：

```python
EPS = 0.5  # 坐标比较容差（px）
```

在 `check_layout` 函数之后加入：

```python
def _fits(box, w: float, h: float) -> bool:
    x, y, bw, bh = box
    return x >= -EPS and y >= -EPS and x + bw <= w + EPS and y + bh <= h + EPS


def check_geometry(f: str, tpl: dict) -> list[str]:
    """spec 7.1 第 6 条：元素落在绘制区域内；grid 的 item 按 maxItems 算出的最小单元格放得下。"""
    errs = []
    standard = tpl["frame"] == "standard"
    w, h = (REF_W, REF_H) if standard else (CANVAS_W, CANVAS_H)
    area = "body 区" if standard else "画布"
    for i, el in enumerate(tpl["layout"]):
        box = resolve_box(el["box"], w, h)
        if not _fits(box, w, h):
            errs.append(f"{f}  /layout/{i}/box  超出 {area} {w}×{h}")
        if el["type"] != "grid":
            continue
        n = (slot_at(tpl["slots"], el["bind"]) or {}).get("maxItems")
        if not n:
            continue  # 缺 maxItems 已由 check_layout 报告
        cols, gap = el["columns"], el.get("gap", 0)
        rows = math.ceil(n / cols)
        cw = (box[2] - gap * (cols - 1)) / cols
        ch = (box[3] - gap * (rows - 1)) / rows
        for j, sub in enumerate(el["item"]):
            if not _fits(resolve_box(sub["box"], cw, ch), cw, ch):
                errs.append(f"{f}  /layout/{i}/item/{j}/box  按 maxItems={n} 计算的单元格 {cw:.0f}×{ch:.0f} 放不下")
    return errs


def check_example(rel: str, tpl: dict, example) -> list[str]:
    """spec 7.1 第 8 条：example 通过 slots；绑定到组件的数据还要通过组件自己的 schema。"""
    f = f"{rel}/example.yaml"
    problems = [f"{f}  {e}" for e in schema_errors(tpl["slots"], example)]
    if problems:
        return problems

    def walk(elements, scope, prefix):
        for el in elements:
            if "bind" not in el:
                continue
            value = lookup(scope, el["bind"])
            here = prefix if el["bind"] == "." else (*prefix, *el["bind"].split("."))
            if el["type"] == "component" and el["component"] in COMPONENTS and value is not None:
                problems.extend(f"{f}  {e}（组件 {el['component']}）"
                                for e in schema_errors(COMPONENTS[el["component"]].schema, value, prefix=here))
            elif el["type"] == "grid" and isinstance(value, list):
                for j, item in enumerate(value):
                    walk(el["item"], item, (*here, j))

    walk(tpl["layout"], example, ())
    return problems
```

在 `validate_repo` 中：

1. 紧接 `report.errors += check_layout(f, tpl, colors, texts)` 之后加入：

```python
        report.errors += check_geometry(f, tpl)
```

2. 把

```python
        if not (tdir / "example.yaml").is_file():
            report.errors.append(f"{rel}  缺少 example.yaml")
```

替换为

```python
        if (tdir / "example.yaml").is_file():
            report.errors += check_example(rel, tpl, load_yaml(tdir / "example.yaml"))
        else:
            report.errors.append(f"{rel}  缺少 example.yaml")
```

- [ ] **Step 4: 运行全部测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add src/ppt_templates/validate.py tests/test_validate.py
git commit -m "Validate layout geometry and template examples" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: catalog 与 CLI（validate / catalog / list / show）

**Files:**
- Create: `src/ppt_templates/catalog.py`
- Create: `catalog.json`（由命令生成）
- Modify: `src/ppt_templates/cli.py`（整文件替换）
- Modify: `src/ppt_templates/validate.py`（catalog 是否最新）
- Modify: `tests/conftest.py`（`make_repo` 生成 catalog）
- Modify: `AGENTS.md`、`docs/superpowers/specs/2026-10-08-ppt-template-repo-design.md`
- Test: `tests/test_catalog.py`（新）、`tests/test_cli.py`（新）、`tests/test_repo.py`（整文件替换）

**Interfaces:**
- Consumes: `validate.validate_repo`（Task 3–5）、`slots.prepare_pages`、`loader.load_style`
- Produces:
  - `catalog.build_catalog(root) -> list[dict]`，每条字段顺序：`id, topic, also_fits, name, roles, density, [level], tags, when_to_use, slots{required, optional}`
  - `catalog.catalog_text(root) -> str`、`catalog.write_catalog(root) -> Path`、`catalog.catalog_is_current(root) -> bool`、`catalog.load_catalog(root) -> list[dict]`
  - `catalog.filter_catalog(entries, topic=None, role=None, density=None, tag=None) -> list[dict]`（`topic` 同时匹配 `also_fits`）
  - CLI：`ppt validate [deck.yaml]`、`ppt catalog`、`ppt list [--topic] [--role] [--density] [--tag]`（每行 `id\tname\troles逗号分隔\twhen_to_use`）、`ppt show <id>`

- [ ] **Step 1: 写失败的测试**

`tests/test_catalog.py`：

```python
from factories import mini_template
from ppt_templates.catalog import build_catalog, filter_catalog
from ppt_templates.validate import validate_repo


def test_catalog_entry_for_real_template(root):
    entry = next(e for e in build_catalog(root) if e["id"] == "system.solution-layered-arch")
    assert entry == {
        "id": "system.solution-layered-arch",
        "topic": "system",
        "also_fits": ["software", "hardware"],
        "name": "分层系统架构方案",
        "roles": ["solution", "feature"],
        "density": "talk",
        "level": "system",
        "tags": ["架构", "分层", "方案"],
        "when_to_use": "介绍系统整体的分层架构，标出本次新增或改动的模块，并配上关键设计和预期收益",
        "slots": {"required": ["title", "layers", "design_points", "benefits"], "optional": ["title_suffix", "takeaway"]},
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
```

`tests/test_cli.py`：

```python
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
```

`tests/test_repo.py` 整文件替换为：

```python
"""对仓库里真实的模板做整体检查：仓库校验无错，每个模板的 example 都能渲染。"""

import pytest
from pptx import Presentation

from factories import deck_of
from ppt_templates.loader import find_repo_root, load_example
from ppt_templates.render import render_deck
from ppt_templates.validate import validate_repo


def test_repository_is_valid(root):
    assert validate_repo(root).errors == []


def _template_ids(root):
    return [f"{p.parent.parent.name}.{p.parent.name}" for p in sorted((root / "templates").glob("*/*/template.yaml"))]


@pytest.mark.parametrize("tid", _template_ids(find_repo_root()))
def test_every_example_renders(root, tmp_path, tid):
    path = tmp_path / "out.pptx"
    render_deck(deck_of(tid, load_example(root, tid)), root).save(path)
    assert len(Presentation(path).slides) == 1
```

在 `tests/conftest.py` 中：顶部 import 区加入 `from ppt_templates.catalog import write_catalog`；在 `make` 函数的 `return repo` 之前加入一行：

```python
        write_catalog(repo)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_catalog.py tests/test_cli.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'ppt_templates.catalog'`

- [ ] **Step 3: 实现 `catalog.py`**

`src/ppt_templates/catalog.py`：

```python
"""catalog.json：所有模板的精简索引（spec 7.2），由 ppt catalog 生成并提交到仓库。"""

import json
from pathlib import Path

from .errors import PptError
from .loader import load_yaml


def build_catalog(root: Path) -> list[dict]:
    entries = []
    for path in sorted((root / "templates").glob("*/*/template.yaml")):
        tpl = load_yaml(path)
        slots = tpl["slots"]
        required = list(slots.get("required", []))
        entry = {
            "id": tpl["id"],
            "topic": path.parent.parent.name,
            "also_fits": tpl.get("also_fits", []),
            "name": tpl["name"],
            "roles": tpl["roles"],
            "density": tpl.get("density", "talk"),
        }
        if "level" in tpl:
            entry["level"] = tpl["level"]
        entry["tags"] = tpl.get("tags", [])
        entry["when_to_use"] = tpl["when_to_use"]
        entry["slots"] = {
            "required": required,
            "optional": [k for k in slots.get("properties", {}) if k not in required],
        }
        entries.append(entry)
    return entries


def catalog_text(root: Path) -> str:
    return json.dumps(build_catalog(root), ensure_ascii=False, indent=2) + "\n"


def write_catalog(root: Path) -> Path:
    path = root / "catalog.json"
    path.write_text(catalog_text(root), encoding="utf-8")
    return path


def catalog_is_current(root: Path) -> bool:
    path = root / "catalog.json"
    return path.is_file() and path.read_text(encoding="utf-8") == catalog_text(root)


def load_catalog(root: Path) -> list[dict]:
    path = root / "catalog.json"
    if not path.is_file():
        raise PptError("catalog.json 不存在，先运行 uv run ppt catalog")
    return json.loads(path.read_text(encoding="utf-8"))


def filter_catalog(entries, topic=None, role=None, density=None, tag=None) -> list[dict]:
    """按条件筛选；topic 同时匹配主题和 also_fits，未给的条件不参与筛选。"""
    def keep(e):
        return ((topic is None or topic == e["topic"] or topic in e["also_fits"])
                and (role is None or role in e["roles"])
                and (density is None or density == e["density"])
                and (tag is None or tag in e["tags"]))

    return [e for e in entries if keep(e)]
```

- [ ] **Step 4: 仓库校验检查 catalog 是否最新**

在 `src/ppt_templates/validate.py` 的 import 区加入 `from .catalog import catalog_is_current`；在 `validate_repo` 末尾的 `return report` 之前加入：

```python
    if not report.errors and not catalog_is_current(root):
        report.errors.append("catalog.json 不是最新的（运行 uv run ppt catalog）")
```

- [ ] **Step 5: 改写 `cli.py`**

`src/ppt_templates/cli.py` 整文件替换为：

```python
"""ppt 命令行：render / preview / validate / catalog / list / show。"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from .catalog import filter_catalog, load_catalog, write_catalog
from .errors import PptError
from .loader import find_repo_root, load_deck, load_example, load_style, template_dir
from .preview import render_pngs
from .render import render_deck
from .slots import prepare_pages
from .validate import validate_repo


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


def _validate(args) -> None:
    root = find_repo_root()
    if args.deck:
        deck = load_deck(Path(args.deck))
        pages = prepare_pages(deck, root)
        load_style(root, deck.get("style", "default"))
        print(f"deck 校验通过：{len(pages)} 页")
        return
    report = validate_repo(root)
    for warning in report.warnings:
        print(f"警告  {warning}", file=sys.stderr)
    if report.errors:
        raise PptError("\n".join(report.errors))
    print(f"校验通过：{len(list((root / 'templates').glob('*/*/template.yaml')))} 个模板")


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

    args = parser.parse_args(argv)
    try:
        args.run(args)
    except PptError as e:
        print(e, file=sys.stderr)
        return 1
    return 0
```

- [ ] **Step 6: 生成 catalog.json**

Run: `uv run ppt catalog`
Expected: 输出 `.../catalog.json`；文件里有一条 `system.solution-layered-arch`

- [ ] **Step 7: 运行全部测试和仓库校验，确认通过**

Run: `uv run pytest -q && uv run ppt validate`
Expected: 测试全部 PASS；最后一行输出 `校验通过：1 个模板`

- [ ] **Step 8: 更新 AGENTS.md**

把 `AGENTS.md`「## 命令」一节里从 `Python 3.13 + python-pptx，用 uv 管理环境` 开始、到 `` `out/` 和 `preview/` 是本地输出目录，已加入 .gitignore。`` 为止的全部内容（含这两行）替换为：

````markdown
Python 3.13 + python-pptx，用 uv 管理环境（`uv sync` 安装依赖）。已实现：

```
uv run ppt list [--topic T] [--role R] [--density D] [--tag X]   # --topic 同时匹配 also_fits
uv run ppt show <id>                     # 模板定义 + 示例内容
uv run ppt validate                      # 校验仓库：taxonomy、风格、模板、catalog 是否最新
uv run ppt validate deck.yaml            # 校验一份 deck
uv run ppt catalog                       # 重新生成 catalog.json
uv run ppt render deck.yaml -o out/x.pptx
uv run ppt preview deck.yaml -o dir/     # 每页一张 PNG（soffice → PDF → pypdfium2）
uv run ppt preview <id> --write          # 用 example.yaml 重新生成该模板的 preview.png
uv run pytest                            # 全部测试；找不到 soffice 时跳过预览测试
uv run pytest tests/test_render.py::test_name   # 单个测试
```

计划中（尚未实现）：`uv run ppt mcp`（启动 stdio MCP server）。

`out/` 和 `preview/` 是本地输出目录，已加入 .gitignore。

## 新增一个模板

1. 选主题和主页功能，建目录 `templates/<topic>/<roles[0]>-<形态>/`。
2. 参照 `templates/system/solution-layered-arch/` 写 `template.yaml` 和 `example.yaml`。
3. `uv run ppt validate`，按报错修到没有错误。
4. `uv run ppt preview <id> --write` 生成 `preview.png`，打开看有没有溢出、重叠、没对齐。
5. `uv run ppt catalog` 重新生成索引。
6. `uv run pytest`，然后把 `template.yaml`、`example.yaml`、`preview.png`、`catalog.json` 一起提交。
````

同时把 `AGENTS.md` 中的

```
- `slots` 的每个顶层属性都必须被渲染（由页框或恰好一个 `layout` 元素绑定），否则校验报错。
```

改为

```
- `slots` 的每个顶层属性都必须被渲染（由页框渲染，或被 `layout` 元素绑定它或它的子路径），同一路径不能被两个顶层元素重复绑定，否则校验报错。
```

- [ ] **Step 9: 同步 spec 的两处规则措辞**

在 `docs/superpowers/specs/2026-10-08-ppt-template-repo-design.md` 中：

把

```
   - 其余每个顶层属性必须被 `layout` 中恰好一个元素绑定；绑定一个对象或数组即视为渲染了它的全部子字段。
```

改为

```
   - 其余每个顶层属性必须被 `layout` 中的元素绑定（绑定它或它的子路径都算）；同一路径不能被两个顶层元素重复绑定。绑定一个对象或数组即视为渲染了它的全部子字段。
```

把

```
   - `bind` 的槽位类型必须符合 4.3 的表格；绑定组件时，槽位 Schema 必须与组件声明的 Schema 兼容。
```

改为

```
   - `bind` 的槽位类型必须符合 4.3 的表格；绑定组件时，槽位的顶层类型必须与组件 Schema 一致，并且 `example.yaml` 里对应的数据必须通过组件 Schema（用示例数据代替 Schema 之间的兼容性推导）。
```

把

```
每个组件在代码里声明自己接受的数据 Schema，校验器用它检查被绑定槽位的 Schema 是否兼容。
```

改为

```
每个组件在代码里声明自己接受的数据 Schema，校验器用它检查模板 `example.yaml` 中被绑定的数据。
```

- [ ] **Step 10: 提交**

```bash
git add src/ppt_templates/catalog.py src/ppt_templates/cli.py src/ppt_templates/validate.py catalog.json tests/conftest.py tests/test_catalog.py tests/test_cli.py tests/test_repo.py AGENTS.md docs/superpowers/specs/2026-10-08-ppt-template-repo-design.md
git commit -m "Add catalog and validate/catalog/list/show commands" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `bullets` 布局元素

**Files:**
- Modify: `src/ppt_templates/draw.py`（`_emu_box` → `emu_box`、`_add_run` → `add_run`；新增 `add_bullets`）
- Modify: `src/ppt_templates/render.py`（处理 `bullets`）
- Modify: `tests/factories.py`（新增 `bullets_template`）
- Test: `tests/test_bullets.py`（新）

**Interfaces:**
- Consumes: `make_repo`（Task 3/6）、`validate.validate_repo`、`factories.deck_of`
- Produces:
  - `draw.emu_box(box) -> tuple[Emu, Emu, Emu, Emu]`、`draw.add_run(p, style, text, text_style, color=None, bold=None)`（Task 8、9 使用）
  - `draw.add_bullets(slide, style, box, items, text_style, *, color=None)`：`items` 为字符串列表或 `{text, level}` 列表；每级缩进一个字宽；第二项起段前 4pt
  - `factories.bullets_template() -> tuple[dict, dict]`（id 为 `common.summary-points`）

- [ ] **Step 1: 写测试工厂和失败的测试**

在 `tests/factories.py` 末尾追加：

```python
def bullets_template():
    """common.summary-points：要点列表（bullets 元素）。"""
    template = {
        "id": "common.summary-points",
        "name": "要点总结",
        "roles": ["summary"],
        "when_to_use": "测试用：要点列表",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "points"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "points": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 8,
                    "items": {
                        "type": "object",
                        "required": ["text"],
                        "properties": {
                            "text": {"type": "string", "maxLength": 40},
                            "level": {"type": "integer", "minimum": 0, "maximum": 2, "default": 0},
                        },
                    },
                },
            },
        },
        "layout": [{"type": "bullets", "box": [0, 0, 800, 400], "bind": "points", "style": "body"}],
    }
    example = {
        "title": "要点总结",
        "points": [
            {"text": "检查点写入不再阻塞训练"},
            {"text": "先写本地 NVMe，再异步下刷", "level": 1},
            {"text": "恢复时间缩短70%"},
        ],
    }
    return template, example
```

`tests/test_bullets.py`：

```python
from pptx import Presentation
from pptx.oxml.ns import qn

from factories import bullets_template, deck_of
from ppt_templates.render import render_deck
from ppt_templates.validate import validate_repo


def test_bullets_render_with_bullet_char_indent_and_spacing(make_repo, tmp_path):
    template, example = bullets_template()
    repo = make_repo({"common.summary-points": (template, example)})
    assert validate_repo(repo).errors == []
    path = tmp_path / "b.pptx"
    render_deck(deck_of("common.summary-points", example), repo).save(path)
    box = next(sh for sh in Presentation(path).slides[0].shapes
               if sh.has_text_frame and sh.text_frame.text.startswith("检查点写入"))
    paras = box.text_frame.paragraphs
    assert [p.text for p in paras] == ["检查点写入不再阻塞训练", "先写本地 NVMe，再异步下刷", "恢复时间缩短70%"]
    em = 16 * 9525  # body 12pt = 16px
    assert [int(p._p.pPr.get("marL")) for p in paras] == [em, 2 * em, em]
    assert all(int(p._p.pPr.get("indent")) == -em for p in paras)
    assert all(p._p.pPr.find(qn("a:buChar")).get("char") == "•" for p in paras)
    assert paras[0]._p.pPr.find(qn("a:spcBef")) is None
    assert paras[1]._p.pPr.find(qn("a:spcBef")) is not None
    assert box._element.xpath(".//a:r/a:rPr/a:ea/@typeface") == ["微软雅黑"] * 3
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_bullets.py -v`
Expected: FAIL，`PptError: 不支持的布局元素类型: bullets`

- [ ] **Step 3: 公开两个绘制辅助函数**

Run: `perl -pi -e 's/\b_emu_box\b/emu_box/g; s/\b_add_run\b/add_run/g' src/ppt_templates/draw.py`
Expected: `draw.py` 中不再有 `_emu_box`、`_add_run`（`grep -c "_emu_box\|_add_run" src/ppt_templates/draw.py` 输出 `0`）

- [ ] **Step 4: 实现 `add_bullets`**

在 `src/ppt_templates/draw.py` 的 `add_runs` 函数之后加入：

```python
BULLET = "•"


def add_bullets(slide, style: dict, box: Box, items, text_style: str, *, color=None):
    """要点列表：每项一段，带项目符号；项是字符串，或 {text, level}（level 从 0 起，每级多缩进一个字宽）。"""
    tb = slide.shapes.add_textbox(*emu_box(box))
    _setup_frame(tb.text_frame, "top", 0)
    em = px_to_emu(_text_style(style, text_style)["size"] * 96 / 72)
    for i, item in enumerate(items):
        text, level = (item, 0) if isinstance(item, str) else (item["text"], item.get("level", 0))
        p = tb.text_frame.paragraphs[0] if i == 0 else tb.text_frame.add_paragraph()
        p_pr = p._p.get_or_add_pPr()
        p_pr.set("marL", str(em * (level + 1)))
        p_pr.set("indent", str(-em))
        if i:  # a:pPr 子元素顺序：spcBef 必须在 buFont / buChar 之前
            p_pr.append(parse_xml(f'<a:spcBef {nsdecls("a")}><a:spcPts val="400"/></a:spcBef>'))
        p_pr.append(parse_xml(f'<a:buFont {nsdecls("a")} typeface="{style["fonts"]["latin"]}"/>'))
        p_pr.append(parse_xml(f'<a:buChar {nsdecls("a")} char="{BULLET}"/>'))
        add_run(p, style, text, text_style, color)
    return tb
```

- [ ] **Step 5: `render.py` 处理 `bullets`**

在 `src/ppt_templates/render.py` 中：

1. 把 `from .draw import add_runs, add_shape, add_text` 改为 `from .draw import add_bullets, add_runs, add_shape, add_text`。
2. 在 `_render_elements` 中 `elif kind == "grid":` 分支之前加入：

```python
        elif kind == "bullets":
            items = lookup(scope, el["bind"])
            if items:
                add_bullets(slide, style, tf(ref_box), items, el["style"], color=el.get("color"))
```

- [ ] **Step 6: 运行全部测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 7: 提交**

```bash
git add src/ppt_templates/draw.py src/ppt_templates/render.py tests/factories.py tests/test_bullets.py
git commit -m "Add bullets layout element" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: `table` 组件

**Files:**
- Create: `src/ppt_templates/components/table.py`
- Modify: `src/ppt_templates/components/__init__.py`（注册）
- Modify: `tests/factories.py`（新增 `table_template`）
- Test: `tests/test_table.py`（新）

**Interfaces:**
- Consumes: `draw.ALIGN`、`draw.emu_box`、`draw.add_run`、`draw.rgb`（Task 7）；`components.Component`（Task 4）
- Produces:
  - `table.SCHEMA`：`{columns: [string], rows: [[string]], highlight_column?: integer}`
  - `table.render(slide, style, box, data, props)`：`props.first_column_width`（px，可选）
  - `factories.table_template() -> tuple[dict, dict]`（id 为 `common.overview-table`）

- [ ] **Step 1: 写测试工厂和失败的测试**

在 `tests/factories.py` 末尾追加：

```python
def table_template():
    """common.overview-table：对比表格（table 组件），高亮推荐列。"""
    template = {
        "id": "common.overview-table",
        "name": "对比表格",
        "roles": ["overview"],
        "when_to_use": "测试用：对比表格",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "matrix"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "matrix": {
                    "type": "object",
                    "required": ["columns", "rows"],
                    "properties": {
                        "columns": {"type": "array", "minItems": 2, "maxItems": 5,
                                    "items": {"type": "string", "maxLength": 8}},
                        "rows": {"type": "array", "minItems": 1, "maxItems": 8,
                                 "items": {"type": "array", "items": {"type": "string", "maxLength": 16}}},
                        "highlight_column": {"type": "integer", "minimum": 0},
                    },
                },
            },
        },
        "layout": [{"type": "component", "component": "table", "box": [0, 0, 1216, 360],
                    "bind": "matrix", "props": {"first_column_width": 200}}],
    }
    example = {
        "title": "存储介质选型",
        "matrix": {
            "columns": ["指标", "SATA SSD", "NVMe SSD", "CXL 内存"],
            "rows": [["带宽", "0.5 GB/s", "7 GB/s", "64 GB/s"],
                     ["延迟", "100 μs", "20 μs", "0.3 μs"],
                     ["单价", "低", "中", "高"]],
            "highlight_column": 2,
        },
    }
    return template, example
```

`tests/test_table.py`：

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_table.py -v`
Expected: FAIL（校验报 `/layout/0/component  未知组件 table`，或渲染时报未知组件）

- [ ] **Step 3: 实现 `table.py`**

`src/ppt_templates/components/table.py`：

```python
"""表格 / 对比矩阵：原生 PPT 表格。表头深色底，正文行浅色交替，可高亮一列（如推荐方案）。"""

from pptx.enum.text import MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Emu

from ..draw import ALIGN, add_run, emu_box, rgb
from ..errors import PptError
from ..geometry import px_to_emu

NO_STYLE_NO_GRID = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # 去掉内置表格样式，颜色全部由风格 token 决定
CELL_PAD = 6

SCHEMA = {
    "type": "object",
    "required": ["columns", "rows"],
    "properties": {
        "columns": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "rows": {"type": "array", "minItems": 1, "items": {"type": "array", "items": {"type": "string"}}},
        "highlight_column": {"type": "integer", "minimum": 0},
    },
}


def _cell(cell, style, text, text_style, fill, *, color=None, bold=None, align="left"):
    cell.fill.solid()
    cell.fill.fore_color.rgb = rgb(style, fill)
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = cell.margin_right = Emu(px_to_emu(CELL_PAD))
    cell.margin_top = cell.margin_bottom = Emu(px_to_emu(CELL_PAD / 2))
    cell.text_frame.word_wrap = True
    p = cell.text_frame.paragraphs[0]
    p.alignment = ALIGN[align]
    add_run(p, style, text, text_style, color, bold)


def _widths(total: float, n: int, first) -> list[float]:
    if first and n > 1:
        return [first] + [(total - first) / (n - 1)] * (n - 1)
    return [total / n] * n


def render(slide, style, box, data, props):
    columns, rows = data["columns"], data["rows"]
    for i, row in enumerate(rows):
        if len(row) != len(columns):
            raise PptError(f"表格第 {i + 1} 行有 {len(row)} 格，表头有 {len(columns)} 列")
    hot = data.get("highlight_column")
    _, _, w, h = box
    shape = slide.shapes.add_table(len(rows) + 1, len(columns), *emu_box(box))
    table = shape.table
    table.first_row = table.horz_banding = False
    table._tbl.tblPr.find(qn("a:tableStyleId")).text = NO_STYLE_NO_GRID
    for col, cw in zip(table.columns, _widths(w, len(columns), props.get("first_column_width"))):
        col.width = Emu(px_to_emu(cw))
    for row in table.rows:
        row.height = Emu(px_to_emu(h / (len(rows) + 1)))

    for c, name in enumerate(columns):
        _cell(table.cell(0, c), style, name, "body_strong", "highlight_strong" if c == hot else "primary",
              color="on_primary", align="center")
    for r, row in enumerate(rows, 1):
        fill = "surface" if r % 2 == 0 else "bg"
        for c, text in enumerate(row):
            if c == hot:
                _cell(table.cell(r, c), style, text, "body", "highlight", color="highlight_strong", bold=True, align="center")
            elif c == 0:
                _cell(table.cell(r, c), style, text, "body_strong", fill)
            else:
                _cell(table.cell(r, c), style, text, "body", fill, align="center")
    return shape
```

- [ ] **Step 4: 注册组件**

`src/ppt_templates/components/__init__.py` 中：

1. 把 `from . import layered_arch` 改为 `from . import layered_arch, table`。
2. 在 `COMPONENTS` 字典里加一项：

```python
    "table": Component(table.render, table.SCHEMA),
```

- [ ] **Step 5: 运行全部测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add src/ppt_templates/components tests/factories.py tests/test_table.py
git commit -m "Add table component" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: `block-diagram` 组件

**Files:**
- Create: `src/ppt_templates/components/block_diagram.py`
- Modify: `src/ppt_templates/components/__init__.py`（注册）
- Modify: `tests/factories.py`（新增 `diagram_template`）
- Modify: `AGENTS.md`（当前状态）
- Test: `tests/test_block_diagram.py`（新）

**Interfaces:**
- Consumes: `draw.add_shape`、`draw.add_text`、`draw.rgb`；`geometry.EMU_PER_PX`；`components.Component`
- Produces:
  - `block_diagram.SCHEMA`：`{nodes: [{id, name, pos: [row, col], highlight?}], edges?: [{from, to, label?}]}`
  - `block_diagram.render(slide, style, box, data, props)`
  - `factories.diagram_template() -> tuple[dict, dict]`（id 为 `system.solution-flow`）

- [ ] **Step 1: 写测试工厂和失败的测试**

在 `tests/factories.py` 末尾追加：

```python
def diagram_template():
    """system.solution-flow：数据流框图（block-diagram 组件）。"""
    template = {
        "id": "system.solution-flow",
        "name": "数据流框图",
        "roles": ["solution"],
        "when_to_use": "测试用：数据流框图",
        "frame": "standard",
        "slots": {
            "type": "object",
            "required": ["title", "flow"],
            "properties": {
                "title": {"type": "string", "maxLength": 14},
                "flow": {
                    "type": "object",
                    "required": ["nodes"],
                    "properties": {
                        "nodes": {
                            "type": "array", "minItems": 2, "maxItems": 12,
                            "items": {
                                "type": "object",
                                "required": ["id", "name", "pos"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "name": {"type": "string", "maxLength": 10},
                                    "pos": {"type": "array", "minItems": 2, "maxItems": 2,
                                            "items": {"type": "integer", "minimum": 0}},
                                    "highlight": {"type": "boolean", "default": False},
                                },
                            },
                        },
                        "edges": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["from", "to"],
                                "properties": {"from": {"type": "string"}, "to": {"type": "string"},
                                               "label": {"type": "string", "maxLength": 8}},
                            },
                        },
                    },
                },
            },
        },
        "layout": [{"type": "component", "component": "block-diagram", "box": [0, 0, 1216, 400], "bind": "flow"}],
    }
    example = {
        "title": "检查点写入路径",
        "flow": {
            "nodes": [
                {"id": "gpu", "name": "训练进程", "pos": [0, 0]},
                {"id": "nvme", "name": "本地 NVMe", "pos": [0, 1], "highlight": True},
                {"id": "store", "name": "存储集群", "pos": [0, 2]},
                {"id": "meta", "name": "元数据服务", "pos": [1, 2]},
            ],
            "edges": [
                {"from": "gpu", "to": "nvme", "label": "同步写"},
                {"from": "nvme", "to": "store", "label": "异步下刷"},
                {"from": "store", "to": "meta"},
            ],
        },
    }
    return template, example
```

`tests/test_block_diagram.py`：

```python
import pytest
from pptx import Presentation
from pptx.oxml.ns import qn

from factories import deck_of, diagram_template
from ppt_templates.errors import PptError
from ppt_templates.render import render_deck
from ppt_templates.validate import validate_repo


def test_nodes_and_arrow_connectors(make_repo, tmp_path):
    template, example = diagram_template()
    repo = make_repo({"system.solution-flow": (template, example)})
    assert validate_repo(repo).errors == []
    path = tmp_path / "d.pptx"
    render_deck(deck_of("system.solution-flow", example), repo).save(path)
    shapes = list(Presentation(path).slides[0].shapes)
    node = {sh.text_frame.text: sh for sh in shapes if sh.has_text_frame}
    conns = [sh for sh in shapes if sh._element.tag == qn("p:cxnSp")]
    assert len(conns) == 3
    gpu, nvme, store, meta = node["训练进程"], node["本地 NVMe"], node["存储集群"], node["元数据服务"]
    first, _, last = conns
    assert abs(first.begin_x - (gpu.left + gpu.width)) <= 1 and abs(first.end_x - nvme.left) <= 1      # 水平：右 → 左
    assert abs(last.begin_y - (store.top + store.height)) <= 1 and abs(last.end_y - meta.top) <= 1     # 垂直：下 → 上
    assert all(c._element.xpath(".//a:tailEnd/@type") == ["triangle"] for c in conns)
    assert "同步写" in node and "异步下刷" in node
    assert str(nvme.fill.fore_color.rgb) == "FFF1E6"


@pytest.mark.parametrize("mutate, message", [
    (lambda f: f["edges"].append({"from": "gpu", "to": "ghost"}), "框图连线引用了不存在的节点: ghost"),
    (lambda f: f["nodes"].append({"id": "x", "name": "重叠", "pos": [0, 0]}), r"框图节点位置重复: \[0, 0\]"),
    (lambda f: f["nodes"].append({"id": "gpu", "name": "重复", "pos": [1, 0]}), "框图节点 id 重复: gpu"),
])
def test_bad_references_are_rejected(make_repo, mutate, message):
    template, example = diagram_template()
    mutate(example["flow"])
    repo = make_repo({"system.solution-flow": (template, example)})
    with pytest.raises(PptError, match=message):
        render_deck(deck_of("system.solution-flow", example), repo)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `uv run pytest tests/test_block_diagram.py -v`
Expected: FAIL（未知组件 `block-diagram`）

- [ ] **Step 3: 实现 `block_diagram.py`**

`src/ppt_templates/components/block_diagram.py`：

```python
"""框图 / 流程图：节点按内容给出的 [行, 列] 放进网格，边是节点之间带箭头的直线连接（v1 不做自动布局）。"""

from pptx.enum.shapes import MSO_CONNECTOR
from pptx.oxml import parse_xml
from pptx.oxml.ns import nsdecls
from pptx.util import Pt

from ..draw import add_shape, add_text, rgb
from ..errors import PptError
from ..geometry import EMU_PER_PX

GAP_X, GAP_Y = 48, 32        # 节点之间的水平 / 垂直间距（px），留给连线和标签
LABEL_W, LABEL_H = 120, 16   # 连线标签的文字框
TOP, LEFT, BOTTOM, RIGHT = 0, 1, 2, 3  # 矩形的连接点编号

SCHEMA = {
    "type": "object",
    "required": ["nodes"],
    "properties": {
        "nodes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "name", "pos"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "pos": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer", "minimum": 0}},
                    "highlight": {"type": "boolean"},
                },
            },
        },
        "edges": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["from", "to"],
                "properties": {"from": {"type": "string"}, "to": {"type": "string"}, "label": {"type": "string"}},
            },
        },
    },
}


def _sites(src, dst) -> tuple[int, int]:
    """按两节点的相对位置选连接点：水平方向占优就左右相连，否则上下相连。"""
    (r1, c1), (r2, c2) = src, dst
    if abs(c2 - c1) >= abs(r2 - r1):
        return (RIGHT, LEFT) if c2 > c1 else (LEFT, RIGHT)
    return (BOTTOM, TOP) if r2 > r1 else (TOP, BOTTOM)


def _check(nodes, edges) -> dict:
    by_id, cells = {}, set()
    for n in nodes:
        pos = tuple(n["pos"])
        if n["id"] in by_id:
            raise PptError(f"框图节点 id 重复: {n['id']}")
        if pos in cells:
            raise PptError(f"框图节点位置重复: {list(pos)}")
        by_id[n["id"]] = n
        cells.add(pos)
    for e in edges:
        for end in ("from", "to"):
            if e[end] not in by_id:
                raise PptError(f"框图连线引用了不存在的节点: {e[end]}")
    return by_id


def render(slide, style, box, data, props):
    nodes, edges = data["nodes"], data.get("edges", [])
    by_id = _check(nodes, edges)
    rows = max(n["pos"][0] for n in nodes) + 1
    cols = max(n["pos"][1] for n in nodes) + 1
    x, y, w, h = box
    nw = (w - GAP_X * (cols - 1)) / cols
    nh = (h - GAP_Y * (rows - 1)) / rows

    shapes = {}
    for n in nodes:
        r, c = n["pos"]
        hot = n.get("highlight", False)
        shapes[n["id"]] = add_shape(
            slide, style, (x + c * (nw + GAP_X), y + r * (nh + GAP_Y), nw, nh),
            "highlight" if hot else "bg",
            line="highlight_strong" if hot else "line", line_width=1.5 if hot else 0.75,
            text=n["name"], text_style="body",
            color="highlight_strong" if hot else None, bold=True if hot else None,
            align="center", valign="middle", inset=4)

    for e in edges:
        begin, end = _sites(by_id[e["from"]]["pos"], by_id[e["to"]]["pos"])
        conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, 0, 0, 0, 0)
        conn.begin_connect(shapes[e["from"]], begin)
        conn.end_connect(shapes[e["to"]], end)
        conn.line.color.rgb = rgb(style, "muted")
        conn.line.width = Pt(1)
        conn.line._get_or_add_ln().append(parse_xml(f'<a:tailEnd {nsdecls("a")} type="triangle"/>'))
        if e.get("label"):
            mx = (conn.begin_x + conn.end_x) / 2 / EMU_PER_PX
            my = (conn.begin_y + conn.end_y) / 2 / EMU_PER_PX
            if begin in (LEFT, RIGHT):  # 水平线：标签在线的上方
                label_box = (mx - LABEL_W / 2, my - LABEL_H - 2, LABEL_W, LABEL_H)
            else:                       # 垂直线：标签在线的右侧
                label_box = (mx + 6, my - LABEL_H / 2, LABEL_W, LABEL_H)
            add_text(slide, style, label_box, e["label"], "caption",
                     align="center" if begin in (LEFT, RIGHT) else "left")
```

- [ ] **Step 4: 注册组件**

`src/ppt_templates/components/__init__.py` 中：

1. 把 `from . import layered_arch, table` 改为 `from . import block_diagram, layered_arch, table`。
2. 在 `COMPONENTS` 字典里加一项：

```python
    "block-diagram": Component(block_diagram.render, block_diagram.SCHEMA),
```

- [ ] **Step 5: 运行全部测试，确认通过**

Run: `uv run pytest -q`
Expected: 全部 PASS

- [ ] **Step 6: 更新 AGENTS.md 的「当前状态」**

把 `AGENTS.md`「## 当前状态」下的整段替换为：

```
已实现：`ppt render / preview / validate / catalog / list / show`；布局元素 `text` / `bullets` / `shape` / `grid`；组件 `layered-arch` / `table` / `block-diagram`；仓库级校验（spec 7.1 全部规则）和 catalog。模板目前只有 `system.solution-layered-arch`。尚未实现：母版（`master.pptx`）支持、skill、`ppt mcp`。
```

- [ ] **Step 7: 提交**

```bash
git add src/ppt_templates/components tests/factories.py tests/test_block_diagram.py AGENTS.md
git commit -m "Add block-diagram component" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: 新元素与组件的目视验收

**Files:**
- Create: `tests/test_acceptance.py`

**Interfaces:**
- Consumes: `factories.bullets_template`、`factories.table_template`、`factories.diagram_template`、`make_repo`、`preview.render_pngs`
- Produces: `out/acceptance/slide-01.png`（要点列表）、`slide-02.png`（表格）、`slide-03.png`（框图），供目视检查；`out/` 已在 `.gitignore` 中

- [ ] **Step 1: 写验收测试**

`tests/test_acceptance.py`：

```python
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
```

- [ ] **Step 2: 运行验收测试**

Run: `uv run pytest tests/test_acceptance.py -v`
Expected: PASS（若本机没有 soffice 则 SKIPPED；那就在有 LibreOffice 的机器上做这一步）

- [ ] **Step 3: 目视检查三张图**

用图片查看器（或 Agent 的 Read 工具）打开 `out/acceptance/slide-01.png`、`slide-02.png`、`slide-03.png`，逐项确认：

- 要点列表：项目符号「•」与文字之间有间距；二级要点比一级多缩进一个字宽；行间距均匀。
- 表格：表头深蓝底白字；「NVMe SSD」一列为浅橙底、橙色粗体；正文行白色 / 浅灰交替；首列粗体；文字不溢出单元格。
- 框图：四个节点排成 2 行 3 列（第二行只有右侧一个）；「本地 NVMe」为浅橙底、橙色描边；三条灰色箭头分别从左到右、从左到右、从上到下；「同步写」「异步下刷」标签在水平线上方，不压在线上。

发现问题时，回到对应组件文件修改常量（`GAP_X`、`GAP_Y`、`CELL_PAD`、标签位置等），重跑 Step 2 和 `uv run pytest -q`，直到三张图都符合上面的描述。

- [ ] **Step 4: 提交**

```bash
git add tests/test_acceptance.py
git commit -m "Add visual acceptance render for new elements" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

（若 Step 3 改了组件代码，把改动的组件文件一起加入这次提交。）

---

## 后续计划（本计划完成后再分别撰写）

本 spec 包含几个相互独立的子系统，按「每个计划都能单独产出可用软件」拆成以下几个计划。本计划完成后，按顺序为每一项单独写实现计划。

1. **首批模板（计划 2）**：按主题批量编写模板，每个模板都走 AGENTS.md「新增一个模板」的流程。开写前先和用户确认首批清单（建议先覆盖 `common` 的封面、目录、章节、摘要、决策请求、风险、下一步，以及 `system` / `hardware` / `software` 的问题、选型、方案、效果各一到两个），以及是否需要新增组件（例如时间线、指标卡、对比条形图）。
2. **多模型适配（计划 3）**：`.agents/skills/ppt-templates/SKILL.md` 与 `.claude/skills` 软链（验证 spec 8.1 的两个风险）、`.gemini/settings.json`、`ppt mcp`（stdio MCP server，暴露 `list_templates` / `get_template` / `validate_deck` / `render_deck`）。
3. **品牌风格与母版（计划 4）**：用户的品牌文件到位后，提取颜色等取值写入 `styles/default`（字体、字号保持统一规则不变）；实现 `master.pptx` / `master_layout` 支持，并校验母版为 16:9。
