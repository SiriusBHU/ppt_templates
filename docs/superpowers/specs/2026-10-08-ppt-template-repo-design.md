# PPT 模板仓设计

日期：2026-10-08
状态：待评审

## 1. 目标

建一个页粒度的 PPT 模板库，最终产出原生 `.pptx`。模板要满足三类调用方：

- 带文件 / Shell 能力的 Agent CLI（Claude Code、Codex、Gemini CLI、Cursor 等）
- MCP 客户端
- 人工直接使用

三类调用方走同一条路径：**选模板 → 按模板的 JSON Schema 产出内容 → 交给唯一的渲染器**。模型差异只体现在「谁来写内容」，不体现在调用接口上。

实际的 PPT 是从多个主题、多个页模板里挑页拼装出来的，不存在「一个主题对应一套固定 deck」。

## 2. 术语

| 术语 | 英文 / 字段 | 含义 | 例子 |
|---|---|---|---|
| 主题 | topic | 一级分类，对应业务方向，是目录的第一层 | `insight` 洞察、`product` 产品、`software` 软件系统、`hardware` 硬件系统、`common` 通用 |
| 页模板 | template | 一页的版式 + 内容契约，是目录的第二层 | `software/layered-arch` |
| 页功能 | role | 这一页在叙事里的作用，作为标签，可多值 | `problem` 问题、`analysis` 分析、`solution` 系统方案 |
| 风格 | style | 颜色、字体、字号、页框、母版等视觉 token，与模板正交 | `styles/default` |
| deck | deck | 一份待渲染的 PPT：选定风格 + 有序的页列表 | `deck.yaml` |

「主题」只指 topic。视觉层一律叫「风格」，避免混淆。

## 3. 目录结构

```
taxonomy.yaml                       # 主题、页功能的受控词表（唯一来源）
styles/<style>/
    style.yaml                      # 视觉 token + 页框
    master.pptx                     # 可选，品牌母版，渲染时作为底稿
templates/<topic>/<template>/
    template.yaml                   # 元数据 + 槽位 Schema + 布局
    example.yaml                    # 示例内容，必须通过槽位校验
    preview.png                     # 由 example 渲染生成
schema/
    template.schema.json
    style.schema.json
    deck.schema.json
catalog.json                        # 生成物，所有模板的索引，勿手改
src/ppt_templates/                  # 渲染器、校验器、CLI、组件
tests/
.agents/skills/ppt-templates/SKILL.md   # 跨工具 skill（规范位置）
.claude/skills/ppt-templates -> ../../.agents/skills/ppt-templates
.gemini/settings.json               # 让 Gemini CLI 读取 AGENTS.md
AGENTS.md                           # 仓库规则（规范来源）
CLAUDE.md                           # 引用 AGENTS.md
```

### 3.1 分类规则

- 目录只有两级：`templates/<topic>/<template>/`。
- 模板 id = `<topic>.<template>`，由路径决定，例如 `software.layered-arch`。`template.yaml` 里也写 `id`，方便单独阅读；校验器保证两者一致。
- 模板目录名用 kebab-case，描述版式或内容形态（`layered-arch`、`pain-points`），不重复主题名。
- 页功能 `roles` 必须取自 `taxonomy.yaml`；`tags` 是自由标签，不受控。
- 封面、目录、章节页、总结、结束页放在 `common` 主题下。
- 新增主题或页功能只需改 `taxonomy.yaml`，不需要改代码。

### 3.2 taxonomy.yaml

```yaml
topics:
  - { id: insight,  name: 洞察 }
  - { id: product,  name: 产品 }
  - { id: software, name: 软件系统 }
  - { id: hardware, name: 硬件系统 }
  - { id: common,   name: 通用 }
roles:
  - { id: cover,    name: 封面 }
  - { id: agenda,   name: 目录 }
  - { id: section,  name: 章节页 }
  - { id: problem,  name: 问题,     question: 现状哪里不行，代价多大 }
  - { id: analysis, name: 分析,     question: 为什么会这样，关键因素是什么 }
  - { id: feature,  name: 特性,     question: 我们提供了什么能力 }
  - { id: solution, name: 系统方案, question: 系统怎么构成，怎么工作 }
  - { id: result,   name: 效果,     question: 带来了什么可量化的改变 }
  - { id: summary,  name: 总结 }
  - { id: closing,  name: 结束页 }
```

上面是初始草案，评审时增删。`question` 用来告诉模型这一页要回答什么问题。

## 4. 模板元数据（template.yaml）

一个文件包含四部分：元数据、槽位、布局、写作要点。

```yaml
id: software.layered-arch
name: 分层架构
roles: [solution]
tags: [架构, 分层]
when_to_use: 介绍系统整体的分层架构
when_not_to_use: 只讲单模块内部设计 → software.module-detail
frame: standard                 # standard = 使用风格里的标准页框；none = 整页自由布局（封面等）

slots:                          # 内容契约，本身是 JSON Schema（Draft 2020-12）
  type: object
  required: [title, layers]
  properties:
    title:    { type: string, maxLength: 24 }
    takeaway: { type: string, maxLength: 40, description: 标题下的一句话结论 }
    source:   { type: string, maxLength: 60, description: 页脚的数据来源或备注 }
    layers:
      type: array
      minItems: 3
      maxItems: 5
      items:
        type: object
        required: [name, modules]
        properties:
          name: { type: string, maxLength: 8 }
          modules:
            type: array
            minItems: 1
            maxItems: 6
            items:
              type: object
              required: [name]
              properties:
                name:      { type: string, maxLength: 10 }
                highlight: { type: boolean, default: false }

layout:                         # frame: standard 时坐标以 body 区左上角为原点
  - type: component
    component: layered-arch
    box: [0, 0, 1160, 500]      # [x, y, w, h]，单位是逻辑像素
    bind: layers

guidance:
  - 层从上到下：接入 → 业务 → 平台 → 基础设施
  - 本次新增或改动的模块设 highlight: true
```

数量、长度等约束只写在 `slots` 里，`when_to_use` 和 `guidance` 不重复。

### 4.1 为什么槽位用 JSON Schema

- Claude、GPT、Gemini、Qwen 等模型的结构化输出 / function calling 都以 JSON Schema 描述参数。
- MCP 的 `get_template` 直接返回 `slots`，调用方照此构造 `data`，不需要转换。
- 有标准校验库，错误可以精确定位到字段。

模板文件用 YAML 书写（能写注释、更省 token），解析后的 `slots` 必须是合法 JSON Schema。

Schema 里的 `default` 只是注解。渲染前，渲染器先用 `default` 补全缺失字段。

### 4.2 坐标与样式

- 画布固定为 1280×720 逻辑像素（16:9），所有风格一致。渲染时 1px = 9525 EMU，幻灯片尺寸为 12192000×6858000 EMU。
- `frame: standard`：`layout` 坐标以页框 `body` 区左上角为原点，按参考尺寸 **1160×500** 设计。风格的 `body` 尺寸不同时，渲染器把所有 box 按比例缩放到实际 body 区（字号不缩放）。这样更换风格时模板不用改。
- `frame: none`：`layout` 坐标以画布左上角为原点。
- 字号用 pt。
- 布局里的颜色、字体、文字样式只能引用风格 token（如 `style: body`、`fill: accent`），不允许写死色值或字体名。这是不同模板拼成一份 deck 后风格依然统一的前提。

### 4.3 布局元素与绑定

**绑定（`bind`）**：用点号分隔的路径，相对当前作用域解析。顶层作用域是页的 `data`；在 `grid` 的 `item` 内，作用域是数组的当前项；`bind: .` 表示当前项本身（用于字符串数组）。

| type | 作用 | 绑定的槽位类型 |
|---|---|---|
| `text` | 单段文字 | `string` |
| `bullets` | 要点列表 | `string` 数组，或 `{text, level}` 对象数组 |
| `shape` | 装饰性矩形 / 线条 | 无 |
| `grid` | 把数组的每一项按网格重复排布 | 数组，且必须声明 `maxItems` |
| `component` | 引用渲染器内置组件 | 组件自己定义的数据结构 |

校验器会检查绑定的槽位类型是否符合上表。

首批内置组件：

- `table`：表格 / 对比矩阵
- `layered-arch`：分层架构图
- `block-diagram`：框图 / 流程图。节点位置由内容给出（`pos: [row, col]`），边是节点间的直线连接；v1 不做自动图布局。

每个组件在代码里声明自己接受的数据 Schema，校验器用它检查被绑定槽位的 Schema 是否兼容。

**grid 规则**：

- 列数 = `columns`；行数 = ceil(实际项数 / columns)。
- 单元格宽 = (box 宽 − gap × (列数 − 1)) / 列数；单元格高按行数同理计算。
- `item` 内子元素的 box 以单元格左上角为原点；`w`、`h` 可写 `"100%"`，表示单元格的宽 / 高。
- 校验时按 `maxItems` 算出最小单元格，`item` 内的 box 必须放得下。

`grid` 示例（三栏痛点）：

```yaml
layout:
  - type: grid
    box: [0, 10, 1160, 460]
    bind: points
    columns: 3
    gap: 24
    item:
      - { type: shape, box: [0, 0, "100%", 6], fill: accent }
      - { type: text,  box: [0, 20, "100%", 40], bind: name, style: h3 }
      - { type: text,  box: [0, 70, "100%", 200], bind: detail, style: body }
```

### 4.4 页框（frame）

风格里定义标准页框的固定区域，每个区域包含位置和文字样式：

| 区域 | 内容 | 默认样式 |
|---|---|---|
| `title` | 槽位 `title` | `title` |
| `takeaway` | 槽位 `takeaway` | `subtitle` |
| `body` | `layout` 的绘制区域 | — |
| `source` | 槽位 `source` | `caption` |
| `page_number` | 页码（自动） | `caption` |

- `frame: standard`：页框负责渲染 `title`、`takeaway`、`source` 三个槽位和页码。
- `frame: none`：没有页框元素，也没有页码。`title` 等槽位如果存在，就是普通槽位，必须由 `layout` 绑定。

## 5. 风格（style.yaml）

```yaml
master: master.pptx             # 可选；存在时用它作为底稿
master_layout: Blank            # 使用母版中的哪个版式；省略时用空白版式
colors:  { primary: "#...", accent: "#...", text: "#...", muted: "#...", bg: "#...", highlight: "#..." }
fonts:   { cjk: ..., latin: ... }
text_styles:
  title:    { size: 28, weight: bold, color: text }
  subtitle: { size: 16, color: accent }
  h3:       { size: 16, weight: bold, color: text }
  body:     { size: 14, color: text, line_spacing: 1.3 }
  caption:  { size: 10, color: muted }
frame:
  title:       { box: [60, 36, 1160, 56],  style: title }
  takeaway:    { box: [60, 96, 1160, 32],  style: subtitle }
  body:        { box: [60, 150, 1160, 500] }
  source:      { box: [60, 680, 1000, 24], style: caption }
  page_number: { box: [1120, 680, 100, 24], style: caption }
```

- `style.schema.json` 固定 token 集合：上面列出的颜色名和文字样式名，每个风格都必须完整提供。模板只能引用这个集合里的 token，因此任何模板都能配任何风格渲染。
- 有 `master.pptx` 时，它的幻灯片尺寸必须是 16:9（12192000×6858000 EMU），否则校验失败。
- 具体值从用户提供的品牌文件中提取。文件到位前先用一套中性的占位风格 `styles/default` 开发，之后整体替换，模板不用改。

## 6. deck 格式（统一调用格式）

```yaml
style: default
pages:
  - template: common.cover
    data: { title: 新一代存储系统方案, subtitle: 2026 Q4 评审 }
  - template: insight.market-gap
    data: { title: ..., points: [...] }
  - template: software.layered-arch
    data: { title: ..., layers: [...] }
```

所有调用方最终都产出这个结构：Agent 写文件，MCP 作为工具参数传入，人工手写。

## 7. 渲染器与 CLI

- 语言：Python 3.13，用 python-pptx 渲染，用 uv 管理环境。选 python-pptx 是因为它能打开已有 `.pptx` 作为底稿，直接复用品牌母版，pptxgenjs 做不到。
- 包位置：`src/ppt_templates/`；入口命令为 `ppt`，用 `uv run ppt ...` 运行。

渲染细节：

- 无母版时：新建 Presentation，显式设置幻灯片尺寸为 12192000×6858000 EMU（python-pptx 默认是 4:3），使用空白版式。
- 有母版时：打开 `master.pptx`，删除其中已有的幻灯片，用 `master_layout` 指定的版式新建页面。
- 字体：python-pptx 的 `font.name` 只写拉丁字体（`a:latin`），中文字体需要额外通过 XML 写入 `a:ea`。

| 命令 | 作用 |
|---|---|
| `ppt list [--topic T] [--role R] [--tag X]` | 列出模板（读 catalog） |
| `ppt show <id>` | 输出模板定义和示例内容 |
| `ppt validate` | 校验整个仓库：所有模板、风格、taxonomy，以及 catalog 是否最新 |
| `ppt validate <deck.yaml>` | 校验一份 deck 的内容 |
| `ppt catalog` | 重新生成 `catalog.json` |
| `ppt render <deck.yaml> -o out.pptx` | 渲染 |
| `ppt preview <deck.yaml> -o dir/` | 渲染后转成每页一张 PNG，用于目视检查 |
| `ppt preview <id> [--style S] [--write]` | 用模板的 `example.yaml` 渲染预览，默认风格为 `default`；`--write` 写入该模板目录的 `preview.png` |
| `ppt mcp` | 启动 MCP server（见 8.2） |

预览流程：用 `soffice` 把 `.pptx` 转成 PDF，再用 pypdfium2 把 PDF 每页转成 PNG。直接用 `soffice --convert-to png` 只会输出第一页，不能用。

### 7.1 校验规则

仓库校验：

1. `template.yaml` 符合 `schema/template.schema.json`。
2. `id` 与路径一致；主题目录在 `taxonomy.topics` 中；`roles` ⊂ `taxonomy.roles`。
3. `slots` 是合法的 JSON Schema，顶层为 `type: object`。
4. 槽位与渲染一一对应，只检查 `slots` 的顶层属性：
   - `frame: standard` 时，`title` 必须出现在 `required` 中；`title`、`takeaway`、`source` 若存在，必须是 `type: string`，由页框渲染，`layout` 不得再绑定它们。
   - 其余每个顶层属性必须被 `layout` 中恰好一个元素绑定；绑定一个对象或数组即视为渲染了它的全部子字段。
   - 未被渲染的顶层属性、指向不存在槽位的 `bind`，都报错。
   - `bind` 的槽位类型必须符合 4.3 的表格；绑定组件时，槽位 Schema 必须与组件声明的 Schema 兼容。
5. 所有 box 必须落在绘制区域内：`frame: standard` 为参考 body 区 1160×500，`frame: none` 为画布 1280×720；`grid` 按 4.3 的规则检查。
6. 布局引用的 token 都在 `style.schema.json` 规定的集合内；每个 `styles/*/style.yaml` 都通过 `style.schema.json` 校验。
7. `example.yaml` 通过 `slots` 校验。
8. `catalog.json` 与模板内容一致。

deck 校验：`style` 存在；每页的模板存在；`data` 通过对应 `slots` 校验。错误信息包括人看的页码（从 1 开始）、模板 id、JSON Pointer 路径（从 0 开始）和具体约束，例如：

```
第 4 页 software.layered-arch  /pages/3/data/layers/1/name  长度 11，超过上限 8
```

模型据此即可自行修正，不依赖任何特定模型的能力。

### 7.2 catalog.json

由 `ppt catalog` 生成并提交到仓库，是模型选模板时读的第一份文件，必须保持精简。每个模板一条：

```json
{
  "id": "software.layered-arch",
  "topic": "software",
  "name": "分层架构",
  "roles": ["solution"],
  "tags": ["架构", "分层"],
  "when_to_use": "介绍系统整体的分层架构",
  "slots": { "required": ["title", "layers"], "optional": ["takeaway", "source"] }
}
```

## 8. 调用方适配

```
             ┌─ Agent CLI：SKILL.md 指导流程 → 运行 ppt CLI
deck.yaml ───┼─ MCP 客户端：MCP server 暴露同一组功能
             └─ 人工：手写 deck.yaml → 运行 ppt CLI
                          ↓
                 ppt render（唯一的渲染实现）
```

### 8.1 Skill（Agent Skills 标准）

- 规范位置为 `.agents/skills/ppt-templates/SKILL.md`。Codex、Cursor、Gemini CLI 官方都识别这个目录。
- `.claude/skills/ppt-templates` 软链到上面，供 Claude Code 使用。
- 实现时需要验证两个风险：
  - Cursor 同时扫描 `.claude/skills`，同一个 skill 可能出现两次。
  - Claude Code 历史上对软链的 skill 目录有过发现失败的问题。

  如果软链不可用，就改为由脚本生成副本，并让 `ppt validate` 检查副本与规范位置一致。
- SKILL.md 只写流程，不复制模板内容：
  1. 读 `catalog.json` 或运行 `ppt list`，按页选模板（可跨主题）
  2. 对选中的模板运行 `ppt show`，读槽位和写作要点
  3. 写 `deck.yaml`
  4. 运行 `ppt validate deck.yaml`，按报错修正
  5. 运行 `ppt render`，再用 `ppt preview` 目视检查，有问题就回到第 3 步

### 8.2 MCP server

`ppt mcp` 启动 stdio MCP server，提供以下工具，内部调用与 CLI 相同的函数：

- `list_templates(topic?, role?, tag?)`
- `get_template(id)`：返回元数据、`slots`、`guidance` 和示例
- `validate_deck(deck)`：`deck` 的结构见 `schema/deck.schema.json`
- `render_deck(deck, output_path)`

### 8.3 仓库说明文件

- `AGENTS.md` 是仓库规则的规范来源，Codex、Cursor 直接读取。
- `CLAUDE.md` 通过 `@AGENTS.md` 引用它。
- Gemini CLI 默认读取 `GEMINI.md`，用 `.gemini/settings.json` 的 `context.fileName` 改为读取 `AGENTS.md`。

## 9. 测试

- 单元测试：坐标换算与缩放、grid 计算、各布局元素和组件的渲染结果（形状数量、位置、文字）。
- 仓库测试：对每个模板执行仓库校验，并用其 `example.yaml` 渲染，确认生成的 `.pptx` 能被 python-pptx 重新打开。
- 依赖 `soffice` 的预览测试，在找不到 `soffice` 时自动跳过。
- 用 pytest，运行 `uv run pytest`。

## 10. 分阶段

1. 骨架：`taxonomy.yaml`、三个 JSON Schema、占位风格、校验器、`ppt validate` / `ppt catalog` / `ppt list` / `ppt show`
2. 渲染：python-pptx 渲染器、页框、`text` / `bullets` / `shape` / `grid`、`ppt render` / `ppt preview`；首批模板为 `common` 下的封面和章节页，以及每个业务主题各一个
3. 组件：`table`、`layered-arch`、`block-diagram`
4. 多模型适配：SKILL.md 和软链（验证 8.1 的两个风险）、`.gemini/settings.json`
5. MCP server
6. 品牌风格：用户文件到位后提取 `styles/default`（可与 2–5 并行）

## 11. 待补充输入

- 用户的品牌 / 母版文件：决定 `styles/default` 的取值，以及是否启用 `master.pptx`。
- 用户在「页面元素」里选了「其他」但未说明，确认后再决定是否新增组件。
