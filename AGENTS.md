# AGENTS.md

页粒度的 PPT 模板库，最终产出原生 `.pptx`。所有调用方（Agent CLI、MCP 客户端、人工）走同一条路径：选模板 → 按模板的 JSON Schema 写内容 → 交给唯一的渲染器。完整设计见 `docs/superpowers/specs/2026-10-08-ppt-template-repo-design.md`。

## 当前状态

已实现：`ppt render / preview / validate / catalog / list / show / import / leaks / sync-skill / mcp`；布局元素 `text` / `bullets` / `shape` / `grid` / `image`；组件 `layered-arch` / `partitioned-arch` / `lane-roadmap` / `capability-map` / `table` / `block-diagram`；仓库级校验（spec 7.1 全部规则，外加 skill 副本一致性）和 catalog；skill（`.agents/skills/ppt-templates`、`.agents/skills/pptx-to-template`）和 MCP server。模板清单见 `catalog.json`。尚未实现：母版（`master.pptx`）支持。

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
- 每个模板目录包含三个文件：`template.yaml`（元数据 + `structure` + `slots` + `layout` + `guidance`）、`example.yaml`（必须通过 `slots` 校验）、`preview.png`（由 example 渲染生成，不要手工制作）。
- `structure`（字符串列表）写这一页的逻辑：每个元素承载什么角色（这块文字讲什么、这个框为什么存在——圈住一组文字、给架构图占位……），它们怎么组成一个完整的论证。从样板做的模板必须写；槽位的 `description` 和 example 的引导文字都要和它对上。
- `slots` 本身就是 JSON Schema（Draft 2020-12）。它是模型产出内容的唯一契约，不要在别处另写一份字段说明。
- 数量、长度等约束只写在 `slots` 里，`when_to_use` 和 `guidance` 不重复。
- `layout` 坐标是逻辑像素 `[x, y, w, h]`，字号用 pt。画布固定 1280×720。
  - `frame: standard`：坐标以 body 区左上角为原点，按参考尺寸 1216×560 设计，渲染时缩放到风格的实际 body 区。
  - `frame: none`：坐标以画布左上角为原点。
- 颜色、字体、文字样式只能引用 `style.schema.json` 规定的 token，不能写死色值或字体名——否则从不同模板拼出来的 deck 风格会不统一。
- 所有文字统一用微软雅黑（硬性要求），每个文字 run 的 `a:latin` / `a:ea` / `a:cs` 都要写成微软雅黑。本机没有这个字体时，预览会把它固定替换为冬青黑体（见 `src/ppt_templates/preview.py`），预览图只用来检查排版。
- `frame: standard` 的模板由页框渲染 `title` / `title_suffix` / `takeaway`，`layout` 不得再绑定这三个槽位；不写 `takeaway`（槽位缺失，或这页没填 / 填了空串）时正文区上移到风格的 `frame.body_compact`（默认 `[32, 88, 1216, 600]`：标题下 16px 起，下边缘不变），layout 坐标仍按 1216×560 写、纵向拉伸到 600，字号不缩放，风格没写 `body_compact` 就还用 `body`；上下左右页边距统一 32px，不画页码、数据来源、顶部色条、标题下的分隔线；封面这类整页自由布局的模板用 `frame: none`。
- 字体和字号对所有模板、所有风格统一（硬性要求）：每个文字样式 token 的字号固定在 `schema/style.schema.json` 里，风格不能改，加载风格时检查；模板元素只能用 `style: <token>`，不能写字号或字体。字号只有 24 / 18 / 14 / 12 / 10 / 9 / 8：标题主体 24 + 同一行后半句 18（`title` + `title_suffix`），副标题 18（`subtitle`），正文区的栏目标题 18 加粗（`heading`），重点或总结性文字 14 加粗（`emphasis`），14 号不加粗的要点正文（`lead`），正常文字 12（`body` / `body_strong`），细节 10 / 9 / 8（`detail` / `caption` / `footnote`）。模板通过这些 token 选字号，不直接写数字。
- `slots` 的每个顶层属性都必须被渲染（由页框渲染，或被 `layout` 元素绑定它或它的子路径），同一路径不能被两个顶层元素重复绑定，否则校验报错。`bind` 是点号路径，相对当前作用域解析：顶层是页的 `data`，`grid` 的 `item` 内是当前项，`.` 表示当前项本身。
- `grid.columns` 是列数上限（实际列数 = min(columns, 项数)，项少时占满整行），`row_height` 固定行高、从顶部排起；`weight: <相对每项的点号路径>` 按每项这个数值（指向数组时按条目数，没填按 1）分配：单列 grid 分行高，多列 grid 每行的项按权重占满整行宽——权重槽位必须是带 `minimum`（> 0）和 `maximum` 的 number，或带 `minItems`（≥ 1）和 `maxItems` 的数组，校验按最不利的比例检查单元格；任何元素可用 `when: <点号路径>`，值为 null / "" / [] / {} 时不渲染；颜色随数据变化用 `color_map`（text）或 `by` + `fill_map` / `line_map`（shape），形式 `{值: 颜色 token}`，值先转字符串再匹配，取值槽位有 `enum` 时键必须在其内。
- `grid` 的 `item` 内可用 `bind: "#"` 取当前项的序号（从 1 起，字符串，只能绑定给 `text`）；在 `item` 之外使用会报错，也不算对槽位的绑定。
- `grid` 的 `item` 里可以再放 `grid`（嵌套任意层）：内层 `bind` 相对外层当前项解析，内层 `columns` / `row_height` 各自生效，`#` 是内层 grid 的序号；校验按外层最小单元格逐层检查 box，指针形如 `/layout/0/item/1/item/0/box`。
- `image` 元素 `{type: image, box, bind, placeholder, fit?: contain | cover, when?}`：`bind` 指向 string 槽位（图片路径），`placeholder`（必填）是引导文字。值缺失或为空串时画 `surface` 底、无阴影的矩形，居中写 `placeholder`（`detail`、`text` 色）——`example.yaml` 一般留空，预览图就是这个占位框；有值时把图片放进 box，`contain`（默认）等比缩放、居中，`cover` 等比铺满并裁掉超出部分。支持 png / jpg / jpeg / gif / bmp / tiff。路径相对 deck 文件所在目录（模板的 `example.yaml` 和 `ppt preview <id>` 相对模板目录），CLI 可写绝对路径；deck 校验时文件不存在、扩展名不支持或读不出图片会报中文错误，如 `/pages/0/data/photo  图片 a.png 不存在`。可用在 grid 的 `item` 里，槽位计入「已渲染」「不得重复绑定」。
- `text` 除 `bind` / `value` 外可写 `runs: [{bind | value, style?, color?}]`（三者有且只有一个），在同一个段落里连排多个 run 并一起折行，如「加粗名称：」+ 正常说明；run 没写 `style` / `color` 就用元素的，run 的 `bind` 与元素的 `bind` 一样在当前作用域解析（`#` 可用）、一样计入「槽位已渲染」和「不得重复绑定」；`runs` 可以写 `by` + `color_map` 给没写 `color` 的 run 按值取色，`when` 作用于整个元素。
- `shape: rounded` 可写 `radius: <px>` 固定圆角大小（不写则用 PowerPoint 默认，圆角随短边按比例变大）；`bullets` 写 `marker: false` 时不画项目符号、不缩进，只是段与段之间留间距（卡片里并列的几段说明）。
- `bullets` 的项可以是 `{text, name?, highlight?, level?}`：`name` 写成段首加粗的「名称：」，`highlight` 写成段尾蓝色加粗的强调片段；写 `children: <字段>` 时绑定的是分组数组，每组先写一段加粗的组名（取 `name`，自动接「：」，字号用 `group_style`），再写这一组 `<字段>` 里的要点，整列在一个文本框里自然往下排（不用 grid 等分高度）；`by` + `color_map` 按值给整个列表取色。
- `shape` 写 `dash: true`（需要 `line`）时描边画成虚线。
- `shape` 写 `shadow: true` 画卡片投影，样式（颜色 token、alpha、blur / distance 像素、angle 度）只来自风格的 `shadow` 小节，模板不能自己写；风格没有 `shadow` 时渲染报错。
- YAML 按 1.2 读取：只有 `true` / `false` 是布尔，`yes` / `no` / `on` / `off` 都是字符串（所以 `no:` 可以当字段名，布尔字段写 `yes` 会被 schema 拒绝）。
- 表格、架构图、框图这类复杂元素不在 YAML 里逐个画框，而是引用 `src/ppt_templates/` 中的内置组件（`table`、`layered-arch`、`partitioned-arch`、`lane-roadmap`、`capability-map`、`block-diagram`）。组件自带数据 Schema、`props` Schema 和语义检查，模板 `example.yaml` 与 deck 的数据、layout 的 `props` 都会按它们校验。照原页调样式用 `props`：`capability-map` 有 `frame`（外框描边，图例留在框外）、`group_fill`、`outline`、`title_color`、`item_style`、`fills`（两类条目的底色）、`legend_look: box`（图例画成带文字的小框）；`table` 有 `look: plain`（白底、只画横线）、`text_style`、`align`、`rule`，数据里可写 `widths` 给各列相对宽度。需要新的复杂元素时，新增组件，而不是在模板里堆 shape。
- 从样板做模板时，形状和文字的样式照原页：描边还是阴影、圆角还是直角、底色、文字对齐方式都保留，只把颜色、字号换成最接近的 token（颜色和字号的硬性规则不变）。下面的约定用于从零设计的模板，以及原页没交代的地方。
- 风格约定（用户定的 house style，新模板默认遵守，不要等用户逐页再提）：
  - 文字颜色只用三种：深红（`accent` / `highlight_strong`）、纯蓝（`primary_text`）、黑（`text`）；靛蓝 `primary` 只做实心色块（表头、封面、层名底色）；`on_primary`（白）只用在深色实心底上；文字不用 `muted` 等其他颜色。`ppt validate` 检查：layout 里 `text` / `bullets` 的 `color`、`color_map` 的值、`runs[].color`，以及风格里每个 `text_styles.*.color`，只能取 `accent` / `highlight_strong` / `primary_text` / `text` / `on_primary`。
  - 标题和短语（名称、标签）加粗（`body_strong` / `emphasis`），成句的说明不加粗。
  - 一个内容块用一张白底带阴影的卡片包住（`fill: bg` + `shadow: true`，不描边）；不画分隔线（竖线、横线、标题下横线）。
  - 「名称：说明」写在同一行，用 `runs`（加粗名称 + 正常说明）；序号用 grid 的 `#`。
  - `example.yaml` 写引导文字（说明这里该填什么，而不是真实内容），每个字符串用到 `maxLength` 的八成左右，让预览体现写满时的效果；文字要填满所在的框，不留半截空行。
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
uv run ppt import SKEL.pptx [--slide N ...] -o DIR   # 骨架 pptx → DIR/slide-N/{shapes.yaml,original.png}，供 agent 照着写模板
uv run ppt leaks <id> SAMPLE.pptx [--slide N ...] [--allow 词]   # example.yaml 和样板原文重合的片段（连续 4 个汉字等），必须 0 处
uv run ppt sync-skill                    # 把 skill 正本复制到 .claude/skills/（改过正本后运行）
uv run ppt mcp                           # 启动 stdio MCP server
uv run pytest                            # 全部测试；找不到 soffice 时跳过预览测试
uv run pytest tests/test_render.py::test_name   # 单个测试
```

`out/` 和 `preview/` 是本地输出目录，已加入 .gitignore。

`ppt import` 的 `shapes.yaml`：`box` 是画布像素，`body_box` 已换算成相对 body 区、按 1216×560 参考尺寸的坐标，可直接写进 layout；`frame_guess.body: compact` 表示这页内容紧贴标题、正文区用 `body_compact`（`body_box` 随之按它换算）；图片和「图片」占位框带 `suggest: image`，提示用 `image` 元素；圆角框带 `radius`（px），照抄成 shape 的 `radius`。

## 新增一个模板

1. 选主题和主页功能，建目录 `templates/<topic>/<roles[0]>-<形态>/`。
2. 参照 `templates/system/solution-arch-overview/` 写 `template.yaml` 和 `example.yaml`。
3. `uv run ppt validate`，按报错修到没有错误。
4. `uv run ppt preview <id> --write` 生成 `preview.png`，打开看有没有溢出、重叠、没对齐。
5. `uv run ppt catalog` 重新生成索引。
6. `uv run pytest`，然后把 `template.yaml`、`example.yaml`、`preview.png`、`catalog.json` 一起提交。

## MCP

`ppt mcp` 以 stdio 方式提供六个工具（实现在 `src/ppt_templates/mcp_server.py`，内部复用 CLI 的同一批函数）：`get_taxonomy`、`list_templates`、`get_template`（不含 `layout`）、`validate_deck`（返回 `{"ok", "errors"}`）、`render_deck`（只写入仓库的 `out/`，`filename` 必须是以 `.pptx` 结尾、不含路径分隔符的文件名）、`preview_deck`（每页一张宽 1280 的 PNG，需要 `soffice`）。image 槽位的图片路径在 MCP 里相对仓库根目录解析，并且只能引用仓库之内的文件（`..`、绝对路径、符号链接解析后落在仓库之外都会被拒绝），因为 deck 来自客户端，不能借它把仓库之外的文件读进 `.pptx` 或预览图。工具失败时返回中文错误。

- Claude Code：仓库根目录的 `.mcp.json` 已配置，按项目加载。
- Claude Desktop 等其他客户端，在它们的 MCP 配置里加：

```json
{"mcpServers": {"ppt-templates": {"command": "uv", "args": ["--directory", "<仓库绝对路径>", "run", "ppt", "mcp"]}}}
```

## Skill 与多模型适配

- 仓库有两个 skill：`ppt-templates`（选模板写 deck）和 `pptx-to-template`（把样板页做成模板）。正本是 `.agents/skills/<name>/SKILL.md`（Codex、Cursor、Gemini CLI 读这里）。Claude Code 只读 `.claude/skills/`，对软链目录的发现不稳定，所以 `.claude/skills/<name>/SKILL.md` 是真实副本。只改正本，改完运行 `uv run ppt sync-skill` 同步全部 skill；`ppt validate` 会检查每个正本的 frontmatter 合法（`name` 与目录名一致）、副本与正本逐字节一致（仓库里没有 `.agents/skills` 时跳过）。新增 skill，把目录名加到 `src/ppt_templates/skill.py` 的 `SKILLS`。
- `pptx-to-template` 把样板或骨架 pptx 做成模板（用 `ppt import` 读形状和原图，`ppt leaks` 检查示例没有带进样板内容）；公司内部侧脱敏的工具是 `tools/ppt-skeleton/`，由用户拷出去用，这里不同步、不运行。
- SKILL.md 只描述流程（排页功能顺序 → 读 catalog 挑模板 → `ppt show` → 写 deck → validate → render → preview），不要把模板内容复制进去。
- 本文件是仓库规则的规范来源，Codex、Cursor 直接读取；`CLAUDE.md` 只是引用本文件；Gemini CLI 通过 `.gemini/settings.json` 指向本文件。
