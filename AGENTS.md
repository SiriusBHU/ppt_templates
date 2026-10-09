# AGENTS.md

页粒度的 PPT 模板库，最终产出原生 `.pptx`。所有调用方（Agent CLI、MCP 客户端、人工）走同一条路径：选模板 → 按模板的 JSON Schema 写内容 → 交给唯一的渲染器。完整设计见 `docs/superpowers/specs/2026-10-08-ppt-template-repo-design.md`。

## 当前状态

已实现：`ppt render / preview / validate / catalog / list / show / sync-skill / mcp`；布局元素 `text` / `bullets` / `shape` / `grid`；组件 `layered-arch` / `table` / `block-diagram`；仓库级校验（spec 7.1 全部规则，外加 skill 副本一致性）和 catalog；skill（`.agents/skills/ppt-templates`）和 MCP server。模板清单见 `catalog.json`。尚未实现：母版（`master.pptx`）支持。

## 术语（不要混用）

- **主题 topic**：一级分类，按「这一页讲的是什么对象」划分，共 12 个：`trend` 行业与技术趋势、`competition` 竞争格局、`ecosystem` 生态与合作、`ipr` 标准与专利、`product` 产品与业务、`workload` 负载分析、`model` 算法与模型、`system` 系统架构、`hardware` 硬件、`software` 软件、`project` 项目与组织、`common` 通用。各主题的边界（`includes` / `excludes`）写在 `taxonomy.yaml`。
- **页模板 template**：单页的版式 + 内容契约，位于 `templates/<topic>/<template>/`。
- **页功能 role**：页在叙事中的作用（problem、selection、solution、result…），是所有主题共用的标签，不是目录，也不是模板名。
- **风格 style**：颜色、字体、字号、页框、母版等视觉 token，位于 `styles/<style>/`。「主题」从不指视觉风格。
- **deck**：`deck.yaml`，选定风格 + 有序页列表。一份 deck 通常从多个主题挑页拼装。

## 结构约定

- 目录只有两级：`templates/<topic>/<template>/`。模板 id = `<topic>.<template>`，由路径决定；`template.yaml` 里的 `id` 必须与路径一致。
- 模板目录名 = `<主页功能>-<形态>`，主页功能就是 `roles[0]`，例如 `hardware/selection-matrix`。阅读型（`density: read`）的目录名末尾加 `-read`。主题 id 和页功能 id 都是单个小写英文单词，不带连字符。
- 归属：按页面主要讲的对象放进一个主题——软硬件协同的整体归 `system`，模型对系统的要求归 `workload`，内容不限的通用版式（数据对比、表格、图文）归 `common`。也适用于其他主题的，用 `also_fits` 声明，不要复制模板。
- `taxonomy.yaml` 是主题和页功能的唯一词表。新增主题或页功能只改这里；模板的 `roles` 必须取自这里，`tags` 不受限制。
- 其他字段：`density`（`talk` 默认 / `read`）、`level`（`system` / `subsystem` / `module`，仅用于 system、hardware、software 主题）。
- 只做中文：槽位的 `maxLength` 按中文字符计。
- 每个模板目录包含三个文件：`template.yaml`（元数据 + `slots` + `layout` + `guidance`）、`example.yaml`（必须通过 `slots` 校验）、`preview.png`（由 example 渲染生成，不要手工制作）。
- `slots` 本身就是 JSON Schema（Draft 2020-12）。它是模型产出内容的唯一契约，不要在别处另写一份字段说明。
- 数量、长度等约束只写在 `slots` 里，`when_to_use` 和 `guidance` 不重复。
- `layout` 坐标是逻辑像素 `[x, y, w, h]`，字号用 pt。画布固定 1280×720。
  - `frame: standard`：坐标以 body 区左上角为原点，按参考尺寸 1216×560 设计，渲染时缩放到风格的实际 body 区。
  - `frame: none`：坐标以画布左上角为原点。
- 颜色、字体、文字样式只能引用 `style.schema.json` 规定的 token，不能写死色值或字体名——否则从不同模板拼出来的 deck 风格会不统一。
- 所有文字统一用微软雅黑（硬性要求），每个文字 run 的 `a:latin` / `a:ea` / `a:cs` 都要写成微软雅黑。本机没有这个字体时，预览会把它固定替换为冬青黑体（见 `src/ppt_templates/preview.py`），预览图只用来检查排版。
- `frame: standard` 的模板由页框渲染 `title` / `title_suffix` / `takeaway`，`layout` 不得再绑定这三个槽位；上下左右页边距统一 32px，不画页码、数据来源、顶部色条；封面这类整页自由布局的模板用 `frame: none`。
- 字体和字号对所有模板、所有风格统一（硬性要求）：每个文字样式 token 的字号固定在 `schema/style.schema.json` 里，风格不能改，加载风格时检查；模板元素只能用 `style: <token>`，不能写字号或字体。字号只有 24 / 18 / 14 / 12 / 10 / 9 / 8：标题主体 24 + 同一行后半句 18（`title` + `title_suffix`），副标题 18（`subtitle`），重点或总结性文字 14（`emphasis`），正常文字 12（`body` / `body_strong`），细节 10 / 9 / 8（`detail` / `caption` / `footnote`）。模板通过这些 token 选字号，不直接写数字。
- `slots` 的每个顶层属性都必须被渲染（由页框渲染，或被 `layout` 元素绑定它或它的子路径），同一路径不能被两个顶层元素重复绑定，否则校验报错。`bind` 是点号路径，相对当前作用域解析：顶层是页的 `data`，`grid` 的 `item` 内是当前项，`.` 表示当前项本身。
- `grid.columns` 是列数上限（实际列数 = min(columns, 项数)，项少时占满整行），`row_height` 固定行高、从顶部排起；任何元素可用 `when: <点号路径>`，值为 null / "" / [] / {} 时不渲染；颜色随数据变化用 `color_map`（text）或 `by` + `fill_map` / `line_map`（shape），形式 `{值: 颜色 token}`，值先转字符串再匹配，取值槽位有 `enum` 时键必须在其内。
- YAML 按 1.2 读取：只有 `true` / `false` 是布尔，`yes` / `no` / `on` / `off` 都是字符串（所以 `no:` 可以当字段名，布尔字段写 `yes` 会被 schema 拒绝）。
- 表格、架构图、框图这类复杂元素不在 YAML 里逐个画框，而是引用 `src/ppt_templates/` 中的内置组件（`table`、`layered-arch`、`block-diagram`）。组件自带数据 Schema、`props` Schema 和语义检查，模板 `example.yaml` 与 deck 的数据、layout 的 `props` 都会按它们校验。需要新的复杂元素时，新增组件，而不是在模板里堆 shape。
- `catalog.json` 是生成物，改动任何模板后都要重新生成，不要手改。

## 命令

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
uv run ppt sync-skill                    # 把 skill 正本复制到 .claude/skills/（改过正本后运行）
uv run ppt mcp                           # 启动 stdio MCP server
uv run pytest                            # 全部测试；找不到 soffice 时跳过预览测试
uv run pytest tests/test_render.py::test_name   # 单个测试
```

`out/` 和 `preview/` 是本地输出目录，已加入 .gitignore。

## 新增一个模板

1. 选主题和主页功能，建目录 `templates/<topic>/<roles[0]>-<形态>/`。
2. 参照 `templates/system/solution-layered-arch/` 写 `template.yaml` 和 `example.yaml`。
3. `uv run ppt validate`，按报错修到没有错误。
4. `uv run ppt preview <id> --write` 生成 `preview.png`，打开看有没有溢出、重叠、没对齐。
5. `uv run ppt catalog` 重新生成索引。
6. `uv run pytest`，然后把 `template.yaml`、`example.yaml`、`preview.png`、`catalog.json` 一起提交。

## MCP

`ppt mcp` 以 stdio 方式提供六个工具（实现在 `src/ppt_templates/mcp_server.py`，内部复用 CLI 的同一批函数）：`get_taxonomy`、`list_templates`、`get_template`（不含 `layout`）、`validate_deck`（返回 `{"ok", "errors"}`）、`render_deck`（只写入仓库的 `out/`，`filename` 必须是以 `.pptx` 结尾、不含路径分隔符的文件名）、`preview_deck`（每页一张宽 1280 的 PNG，需要 `soffice`）。工具失败时返回中文错误。

- Claude Code：仓库根目录的 `.mcp.json` 已配置，按项目加载。
- Claude Desktop 等其他客户端，在它们的 MCP 配置里加：

```json
{"mcpServers": {"ppt-templates": {"command": "uv", "args": ["--directory", "<仓库绝对路径>", "run", "ppt", "mcp"]}}}
```

## Skill 与多模型适配

- Skill 的正本是 `.agents/skills/ppt-templates/SKILL.md`（Codex、Cursor、Gemini CLI 读这里）。Claude Code 只读 `.claude/skills/`，对软链目录的发现不稳定，所以 `.claude/skills/ppt-templates/SKILL.md` 是一份真实副本。只改正本，改完运行 `uv run ppt sync-skill` 同步；`ppt validate` 会检查正本的 frontmatter 合法、副本与正本逐字节一致（仓库里没有 `.agents/skills` 时跳过）。新增别的工具的副本位置，加到 `src/ppt_templates/skill.py` 的 `COPIES`。
- SKILL.md 只描述流程（排页功能顺序 → 读 catalog 挑模板 → `ppt show` → 写 deck → validate → render → preview），不要把模板内容复制进去。
- 本文件是仓库规则的规范来源，Codex、Cursor 直接读取；`CLAUDE.md` 只是引用本文件；Gemini CLI 通过 `.gemini/settings.json` 指向本文件。
