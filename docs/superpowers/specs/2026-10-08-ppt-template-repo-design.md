# PPT 模板仓设计

日期：2026-10-08
状态：待评审（已按主题拷问的结论更新分类部分）

## 1. 目标

建一个页粒度的 PPT 模板库，最终产出原生 `.pptx`。模板要满足三类调用方：

- 带文件 / Shell 能力的 Agent CLI（Claude Code、Codex、Gemini CLI、Cursor 等）
- MCP 客户端
- 人工直接使用

三类调用方走同一条路径：**选模板 → 按模板的 JSON Schema 产出内容 → 交给唯一的渲染器**。模型差异只体现在「谁来写内容」，不体现在调用接口上。

实际的 PPT 是从多个主题、多个页模板里挑页拼装出来的，不存在「一个主题对应一套固定 deck」。

使用背景：

- 汇报对象都在公司内部：高层管理者、技术专家 / 评审、跨部门 / 上下游团队。
- 讲解型（现场讲）为主，阅读型（发出去自己看）为辅。
- 只做中文，允许夹英文术语。

## 2. 术语

| 术语 | 英文 / 字段 | 含义 | 例子 |
|---|---|---|---|
| 主题 | topic | 一级分类，按「这一页讲的是什么对象」划分，是目录的第一层 | `system` 系统架构、`hardware` 硬件（共 12 个，见 3.2） |
| 页模板 | template | 一页的版式 + 内容契约，是目录的第二层 | `software/solution-layered-arch` |
| 页功能 | role | 这一页在叙事里的作用，是所有主题共用的标签，可多值 | `problem` 问题、`selection` 选型、`solution` 方案 |
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

### 3.1 分类与命名规则

**目录与 id**

- 目录只有两级：`templates/<topic>/<template>/`。
- 模板 id = `<topic>.<template>`，例如 `hardware.selection-matrix`。`template.yaml` 里也写 `id`，方便单独阅读；校验器保证两者一致。
- 主题 id 和页功能 id 都是单个小写英文单词（`^[a-z]+$`），因为页功能 id 会出现在目录名里，不能带连字符。

**模板目录名 = `<主页功能>-<形态>`**

- 主页功能就是 `roles` 的第一个，例如 `selection-matrix`、`problem-bottleneck-chart`、`solution-block-diagram`。打开一个主题目录时，同一功能的页会自动排在一起。
- 形态部分用 kebab-case，描述版式或内容形态，不重复主题名。
- 阅读型版本（`density: read`）在目录名末尾加 `-read`，例如 `solution-block-diagram-read`。

**归属规则**

- 按页面主要讲的对象放进一个主题，各主题的边界见 3.2 的 `includes` / `excludes`。
- 同时涉及软件和硬件的整体内容归 `system`；模型对系统 / 硬件提出的要求归 `workload`。
- 内容不限的通用版式（数据对比、表格、图文）归 `common`。测试结果、评测数据用这类版式表达，不单设主题。
- 也适用于其他主题的模板，用 `also_fits` 声明。按主题筛选时，它会同时出现在这些主题下。

**词表**

- 页功能 `roles` 必须取自 `taxonomy.yaml`；`tags` 是自由标签，不受控。
- 不是每个主题都要用齐所有页功能。
- 新增主题或页功能只需改 `taxonomy.yaml`，不需要改代码。

### 3.2 taxonomy.yaml

主题按从外到内排列：

```yaml
topics:
  - id: trend
    name: 行业与技术趋势
    includes: 业界趋势、技术方向（含 AI 技术趋势）、外部环境
    excludes: 具体竞争对手 → competition；标准动态 → ipr
  - id: competition
    name: 竞争格局
    includes: 有哪些玩家、份额、定位、各家路线
    excludes: 针对某个对象的逐项对标 → 该对象所在主题的 benchmark 页
  - id: ecosystem
    name: 生态与合作
    includes: 合作伙伴、开源、开发者社区
  - id: ipr
    name: 标准与专利
    includes: 标准组织与进展、专利布局与全景
  - id: product
    name: 产品与业务
    includes: 业务沙盘、产品现状 / 问题 / 需求 / 规划、客户与场景
    excludes: 系统怎么实现 → system / hardware / software
  - id: workload
    name: 负载分析
    includes: 负载的计算 / 访存 / 通信特征，对系统和硬件的需求（AI 和非 AI 都算）
    excludes: 模型本身 → model
  - id: model
    name: 算法与模型
    includes: 模型结构、原理、训练方法、精度
    excludes: 模型对系统的要求 → workload；AI 趋势 → trend
  - id: system
    name: 系统架构
    includes: 软硬件协同的整体架构、系统瓶颈、演进、系统级创新
    excludes: 只涉及硬件或只涉及软件 → hardware / software
  - id: hardware
    name: 硬件
    includes: 从硬件架构到单板 / 器件：瓶颈、选型、方案
    excludes: 软硬件协同的整体 → system
  - id: software
    name: 软件
    includes: 从软件架构到单个特性 / 模块：问题、方案、收益
    excludes: 软硬件协同的整体 → system
  - id: project
    name: 项目与组织
    includes: 进展、里程碑、人力、组织架构、能力建设
    excludes: 风险、下一步、资源诉求 → common
  - id: common
    name: 通用
    includes: 封面、目录、章节、结束；摘要、决策请求、风险、下一步；内容不限的通用版式（数据对比、表格、图文）
    excludes: 讲具体对象的页 → 对应主题

roles:
  # 内容类
  - { id: overview,    name: 全景 / 现状, question: 现在是什么样 }
  - { id: trend,       name: 趋势,        question: 外部往哪走 }
  - { id: history,     name: 演进回顾,    question: 过去怎么一步步走到现在 }
  - { id: problem,     name: 问题 / 瓶颈, question: 哪里不行，代价多大 }
  - { id: analysis,    name: 分析,        question: 为什么会这样，关键因素是什么 }
  - { id: requirement, name: 需求,        question: 需要满足什么 }
  - { id: benchmark,   name: 对标,        question: 和竞品比差在哪 }
  - { id: selection,   name: 选型,        question: 几个选项里选哪个，为什么 }
  - { id: solution,    name: 方案,        question: 怎么构成，怎么工作 }
  - { id: feature,     name: 特性 / 创新, question: 关键能力和亮点是什么 }
  - { id: result,      name: 效果 / 收益, question: 带来了什么可量化的改变 }
  - { id: roadmap,     name: 规划,        question: 接下来怎么走 }
  # 通用类（主要用于 common 主题）
  - { id: cover,   name: 封面 }
  - { id: agenda,  name: 目录 }
  - { id: section, name: 章节页 }
  - { id: summary, name: 摘要 / 总结 }
  - { id: ask,     name: 决策请求 / 资源诉求 }
  - { id: risk,    name: 风险与应对 }
  - { id: next,    name: 下一步 }
  - { id: closing, name: 结束页 }
```

- `question` 告诉模型这一页要回答什么问题。
- `trend` 同时是主题 id 和页功能 id。两者出现在不同字段里，不会冲突。

## 4. 模板元数据（template.yaml）

一个文件包含四部分：元数据、槽位、布局、写作要点。

```yaml
id: software.solution-layered-arch
name: 分层架构
roles: [solution]               # 第一个是主页功能，必须与目录名前缀一致
also_fits: [system]             # 可选，也适用的其他主题
density: talk                   # talk 讲解型（默认）| read 阅读型
level: system                   # 可选，仅 system / hardware / software 主题使用
tags: [架构, 分层]
when_to_use: 介绍软件整体的分层架构
when_not_to_use: 只讲单模块内部设计 → software.solution-module-detail
frame: standard                 # standard = 使用风格里的标准页框；none = 整页自由布局（封面等）

slots:                          # 内容契约，本身是 JSON Schema（Draft 2020-12）
  type: object
  required: [title, layers]
  properties:
    title:    { type: string, maxLength: 24 }
    title_suffix: { type: string, maxLength: 16, description: 与标题同一行的后半句 }
    takeaway: { type: string, maxLength: 40, description: 副标题，标题下的一句话结论 }
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
    box: [0, 0, 1216, 560]      # [x, y, w, h]，单位是逻辑像素
    bind: layers

guidance:
  - 层从上到下：接入 → 业务 → 平台 → 基础设施
  - 本次新增或改动的模块设 highlight: true
```

字段说明：

- `density`：`talk` 字少图大，现场讲；`read` 信息密，脱离讲解也能看懂。
- `level`：页面讨论对象的粒度。`system` 指整体，`subsystem` 指子系统，`module` 指单个模块 / 特性 / 器件。
- 数量、长度等约束只写在 `slots` 里，`when_to_use` 和 `guidance` 不重复。
- `maxLength` 按中文字符计。

### 4.1 为什么槽位用 JSON Schema

- Claude、GPT、Gemini、Qwen 等模型的结构化输出 / function calling 都以 JSON Schema 描述参数。
- MCP 的 `get_template` 直接返回 `slots`，调用方照此构造 `data`，不需要转换。
- 有标准校验库，错误可以精确定位到字段。

模板文件用 YAML 书写（能写注释、更省 token），解析后的 `slots` 必须是合法 JSON Schema。

Schema 里的 `default` 只是注解。渲染前，渲染器先用 `default` 补全缺失字段。

### 4.2 坐标与样式

- 画布固定为 1280×720 逻辑像素（16:9），所有风格一致。渲染时 1px = 9525 EMU，幻灯片尺寸为 12192000×6858000 EMU。
- `frame: standard`：`layout` 坐标以页框 `body` 区左上角为原点，按参考尺寸 **1216×560** 设计。风格的 `body` 尺寸不同时，渲染器把所有 box 按比例缩放到实际 body 区（字号不缩放）。这样更换风格时模板不用改。
- `frame: none`：`layout` 坐标以画布左上角为原点。
- 字号用 pt。
- 布局里的颜色、字体、文字样式只能引用风格 token（如 `style: body`、`fill: accent`），不允许写死色值或字体名。这是不同模板拼成一份 deck 后风格依然统一的前提。

### 4.3 布局元素与绑定

**绑定（`bind`）**：用点号分隔的路径，相对当前作用域解析。顶层作用域是页的 `data`；在 `grid` 的 `item` 内，作用域是数组的当前项；`bind: .` 表示当前项本身（用于字符串数组）。

| type | 作用 | 绑定的槽位类型 | 其他参数 |
|---|---|---|---|
| `text` | 单段文字 | `string`；也可以不绑定，用 `value` 写固定文字（如小节标题「关键设计」） | `style`、`color`（覆盖文字样式的颜色）、`align`（left / center / right）、`valign`（top / middle / bottom） |
| `bullets` | 要点列表 | `string` 数组，或 `{text, level}` 对象数组 | `style` |
| `shape` | 装饰性矩形 / 线条 | 无 | `fill`、`line`（省略则无边框）、`shape`（rect / rounded） |
| `grid` | 把数组的每一项按网格重复排布 | 数组，且必须声明 `maxItems` | `columns`、`gap`、`item` |
| `component` | 引用渲染器内置组件 | 组件自己定义的数据结构 | `props`：组件的固定选项 |

校验器会检查绑定的槽位类型是否符合上表。

**box 取值**：每一项可以是数字（像素），也可以是 `"N%"`、`"N%+M"`、`"N%-M"`，表示父区域宽（x、w）或高（y、h）的百分比再加减像素。父区域是：`frame: standard` 的 body 区、`frame: none` 的画布、`grid` 内的单元格。

首批内置组件：

- `table`：表格 / 对比矩阵
- `layered-arch`：分层架构图。每层左侧是 120px 的层名块（`primary` 底、`on_primary` 字），右侧是模块区（`surface` 底），模块等宽排成一行。`highlight: true` 的模块用 `highlight` 填充、`highlight_strong` 描边和文字。`props.legend` 有值且存在高亮模块时，在右下角画图例。
- `block-diagram`：框图 / 流程图。节点位置由内容给出（`pos: [row, col]`），边是节点间的直线连接；v1 不做自动图布局。

每个组件在代码里声明自己接受的数据 Schema、`props` Schema，以及 Schema 表达不了的语义检查；校验器用它们检查模板 `example.yaml` 和 deck 中被绑定的数据，以及 layout 里的 `props`。

**grid 规则**：

- 列数 = `columns`；行数 = ceil(实际项数 / columns)。
- 单元格宽 = (box 宽 − gap × (列数 − 1)) / 列数；单元格高按行数同理计算。
- `item` 内子元素的 box 以单元格左上角为原点；`w`、`h` 可写 `"100%"`，表示单元格的宽 / 高。
- 校验时按 `maxItems` 算出最小单元格，`item` 内的 box 必须放得下。

`grid` 示例（三栏痛点）：

```yaml
layout:
  - type: grid
    box: [0, 10, 1216, 500]
    bind: points
    columns: 3
    gap: 24
    item:
      - { type: shape, box: [0, 0, "100%", 6], fill: accent }
      - { type: text,  box: [0, 20, "100%", 40], bind: name, style: emphasis }
      - { type: text,  box: [0, 70, "100%", 200], bind: detail, style: body }
```

### 4.4 页框（frame）

风格里定义标准页框的固定区域，每个区域包含位置和文字样式：

| 区域 | 内容 | 默认样式 |
|---|---|---|
| `title` | 槽位 `title` | `title` |
| `title`（续） | 槽位 `title_suffix`，与标题同一行、共用基线 | `title_suffix`（由 `suffix_style` 指定） |
| `takeaway` | 槽位 `takeaway`（副标题） | `subtitle` |
| `body` | `layout` 的绘制区域 | — |

- 每个区域可以设 `align`。
- 上下左右页边距统一为 32px。不画页码、数据来源等页脚信息，也不画顶部色条。
- 风格里的 `frame.decorations` 是一组 `shape` 元素（画布坐标），比如标题区下方的分隔线。每个 `frame: standard` 页都会先画它们，再画其他内容。
- `frame: standard`：页框负责渲染 `title`、`title_suffix`、`takeaway` 三个槽位。
- `frame: none`：没有页框元素。`title` 等槽位如果存在，就是普通槽位，必须由 `layout` 绑定。

## 5. 风格（style.yaml）

```yaml
master: master.pptx             # 可选；存在时用它作为底稿
master_layout: Blank            # 使用母版中的哪个版式；省略时用空白版式
fonts: { cjk: 微软雅黑, latin: 微软雅黑 }
colors:
  primary: "#..."               # 标题、层名底色
  accent: "#..."                # 结论句、强调条、指标数值
  text: "#..."                  # 正文
  muted: "#..."                 # 次要文字
  line: "#..."                  # 分隔线、边框
  surface: "#..."               # 浅底：卡片、层背景
  bg: "#..."                    # 页面底色
  on_primary: "#..."            # 深色底上的文字
  highlight: "#..."             # 高亮填充（新增 / 改动）
  highlight_strong: "#..."      # 高亮描边和文字
text_styles:                    # 每项：size（pt）、bold（可选）、color（颜色 token）
  title:        { size: 24, bold: true, color: primary }   # 标题主体
  title_suffix: { size: 18, color: primary }               # 与标题同一行的后半句
  subtitle:     { size: 18, color: accent }                # 副标题（一句话结论）
  emphasis:     { size: 14, bold: true, color: text }      # 重点 / 总结性文字、小节标题
  body:         { size: 12, color: text }                  # 正常文字
  body_strong:  { size: 12, bold: true, color: text }      # 正常文字加粗（条目名称等）
  detail:       { size: 10, color: muted }                 # 细节
  caption:      { size: 9, color: muted }                  # 细节：图例、注释
  footnote:     { size: 8, color: muted }                  # 细节：脚注
  kpi:          { size: 24, bold: true, color: accent }    # 指标数值
frame:                          # 上下左右页边距统一 32px
  title:       { box: [32, 32, 1216, 40], style: title, suffix_style: title_suffix }
  takeaway:    { box: [32, 76, 1216, 30], style: subtitle }
  body:        { box: [32, 128, 1216, 560] }
  decorations:
    - { type: shape, box: [32, 116, 1216, 1], fill: line }   # 标题区与正文之间的分隔线
```

当前取值见 `styles/default/style.yaml`。

- **所有文字统一使用微软雅黑**，这是硬性要求：`style.schema.json` 把 `fonts.cjk` 和 `fonts.latin` 都固定为「微软雅黑」，渲染器给每个文字 run 都写入 `a:latin`、`a:ea`、`a:cs`。品牌文件里的字体不采用。
- **字体和字号对所有模板、所有风格统一**：
  - 每个文字样式 token 的字号是固定的（见下表），风格只能改颜色等其他取值，不能改字号和字体。加载风格时检查：文字样式集合必须正好是这些 token，字号必须一一对应。
  - 模板里的元素只能通过 `style` 引用这些 token，`template.schema.json` 禁止在元素上写 `size`、`font` 之类的字段。
  - 字号只有以下几档：

  | 用途 | 字号（pt） | 对应 token |
  |---|---|---|
  | 标题：主体 + 同一行的后半句 | 24 + 18 | `title` + `title_suffix` |
  | 副标题 | 18 | `subtitle` |
  | 重点或总结性文字 | 14 | `emphasis` |
  | 正常文字 | 12 | `body`、`body_strong` |
  | 细节文字 | 10 / 9 / 8 | `detail`、`caption`、`footnote` |

  指标数值 `kpi` 用 24，与标题同档。
- `style.schema.json` 固定 token 集合：上面列出的颜色名和文字样式名，每个风格都必须完整提供。模板只能引用这个集合里的 token，因此任何模板都能配任何风格渲染。
- 有 `master.pptx` 时，它的幻灯片尺寸必须是 16:9（12192000×6858000 EMU），否则校验失败。
- 具体值从用户提供的品牌文件中提取。文件到位前先用一套中性的占位风格 `styles/default` 开发，之后整体替换，模板不用改。

## 6. deck 格式（统一调用格式）

```yaml
style: default
pages:
  - template: common.cover-basic
    data: { title: 新一代存储系统方案, subtitle: 2026 Q4 评审 }
  - template: competition.overview-landscape
    data: { title: ..., players: [...] }
  - template: software.solution-layered-arch
    data: { title: ..., layers: [...] }
  - template: common.ask-decision
    data: { title: ..., asks: [...] }
```

所有调用方最终都产出这个结构：Agent 写文件，MCP 作为工具参数传入，人工手写。

## 7. 渲染器与 CLI

- 语言：Python 3.13，用 python-pptx 渲染，用 uv 管理环境。选 python-pptx 是因为它能打开已有 `.pptx` 作为底稿，直接复用品牌母版，pptxgenjs 做不到。
- 包位置：`src/ppt_templates/`；入口命令为 `ppt`，用 `uv run ppt ...` 运行。

渲染细节：

- 无母版时：新建 Presentation，显式设置幻灯片尺寸为 12192000×6858000 EMU（python-pptx 默认是 4:3），使用空白版式。
- 有母版时：打开 `master.pptx`，删除其中已有的幻灯片，用 `master_layout` 指定的版式新建页面。
- 字体：python-pptx 的 `font.name` 只写拉丁字体（`a:latin`），`a:ea` 和 `a:cs` 需要额外通过 XML 写入。
- 阴影：只设置 `shadow.inherit = False` 时，LibreOffice 仍会画出主题阴影，还要把形状的 `effectRef idx` 设为 0。
- 预览：soffice 每次用一次性的用户配置目录（`-env:UserInstallation`），不和用户已打开的 LibreOffice 冲突。本机没有微软雅黑时，LibreOffice 每次回退的字体都不一样，有时还会用衬线体。所以这个一次性配置里写了字体替换表，把微软雅黑固定替换为 macOS 自带的冬青黑体（Hiragino Sans GB）。这只影响预览，pptx 里写的仍是微软雅黑。预览的字形和实际效果略有差别，但排版可以参考。

| 命令 | 作用 |
|---|---|
| `ppt list [--topic T] [--role R] [--density D] [--tag X]` | 列出模板（读 catalog）。`--topic` 同时匹配 `also_fits` |
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

1. `taxonomy.yaml`：主题 id、页功能 id 都符合 `^[a-z]+$`，且各自不重复。
2. `template.yaml` 符合 `schema/template.schema.json`。其中 `density` 只能是 `talk` / `read`，`level` 只能是 `system` / `subsystem` / `module`。
3. 分类与命名：
   - `id` 与路径一致，主题目录在 `taxonomy.topics` 中。
   - `roles` ⊂ `taxonomy.roles`，目录名以 `<roles[0]>-` 开头。
   - 目录名以 `-read` 结尾，当且仅当 `density: read`。
   - `also_fits` ⊂ `taxonomy.topics`，且不包含模板自己的主题。
   - `level` 只出现在 `system` / `hardware` / `software` 主题的模板里。
4. `slots` 是合法的 JSON Schema，顶层为 `type: object`。
5. 槽位与渲染一一对应，只检查 `slots` 的顶层属性：
   - `frame: standard` 时，`title` 必须出现在 `required` 中；`title`、`title_suffix`、`takeaway` 若存在，必须是 `type: string`，由页框渲染，`layout` 不得再绑定它们。
   - 其余每个顶层属性必须被 `layout` 中的元素绑定（绑定它或它的子路径都算）；同一路径不能被两个顶层元素重复绑定。绑定一个对象或数组即视为渲染了它的全部子字段。
   - 未被渲染的顶层属性、指向不存在槽位的 `bind`，都报错。
   - `bind` 的槽位类型必须符合 4.3 的表格；绑定组件时，槽位的顶层类型必须与组件 Schema 一致，并且 `example.yaml` 里对应的数据必须通过组件 Schema 和语义检查（用示例数据代替 Schema 之间的兼容性推导）；元素的 `props` 必须通过组件的 props Schema。
6. 所有 box 必须落在绘制区域内：`frame: standard` 为参考 body 区 1216×560，`frame: none` 为画布 1280×720；`grid` 按 4.3 的规则检查。
7. 布局引用的 token 都在 `style.schema.json` 规定的集合内；每个 `styles/*/style.yaml` 都通过 `style.schema.json` 校验。
8. `example.yaml` 通过 `slots` 校验。
9. `catalog.json` 与模板内容一致。

deck 校验：`style` 存在；每页的模板存在；`data` 通过对应 `slots` 校验；绑定到组件的数据还要通过组件自己的 Schema 和语义检查（如表格每行格数等于列数、框图节点 id / 位置不重复且连线端点存在、节点不小于 40×24 px），即使 `slots` 写得比组件宽松也一样。错误信息包括人看的页码（从 1 开始）、模板 id、JSON Pointer 路径（从 0 开始）和具体约束，例如：

```
第 4 页 software.solution-layered-arch  /pages/3/data/layers/1/name  长度 11，超过上限 8
```

模型据此即可自行修正，不依赖任何特定模型的能力。

### 7.2 catalog.json

由 `ppt catalog` 生成并提交到仓库，是模型选模板时读的第一份文件，必须保持精简。每个模板一条：

```json
{
  "id": "software.solution-layered-arch",
  "topic": "software",
  "also_fits": ["system"],
  "name": "分层架构",
  "roles": ["solution"],
  "density": "talk",
  "level": "system",
  "tags": ["架构", "分层"],
  "when_to_use": "介绍软件整体的分层架构",
  "slots": { "required": ["title", "layers"], "optional": ["title_suffix", "takeaway"] }
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
  1. 按需求排出页功能顺序（问题 → 分析 → 方案 → 效果……）
  2. 读 `catalog.json` 或运行 `ppt list`，为每一页挑模板（可跨主题）
  3. 对选中的模板运行 `ppt show`，读槽位和写作要点
  4. 写 `deck.yaml`
  5. 运行 `ppt validate deck.yaml`，按报错修正
  6. 运行 `ppt render`，再用 `ppt preview` 目视检查，有问题就回到第 4 步

### 8.2 MCP server

`ppt mcp` 启动 stdio MCP server，提供以下工具，内部调用与 CLI 相同的函数：

- `list_templates(topic?, role?, density?, tag?)`
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
2. 渲染：python-pptx 渲染器、页框、`text` / `bullets` / `shape` / `grid`、`ppt render` / `ppt preview`；首批模板为 `common` 的封面和章节页，再加几个能覆盖 `text` / `bullets` / `grid` 的内容页
3. 组件：`table`、`layered-arch`、`block-diagram`，以及用到它们的模板
4. 多模型适配：SKILL.md 和软链（验证 8.1 的两个风险）、`.gemini/settings.json`
5. MCP server
6. 品牌风格：用户文件到位后提取 `styles/default`（可与 2–5 并行）

## 11. 范围外

- 不做：对外 / 客户类主题、成本与供应链主题、单独的测试或评测主题、英文版本。
- 推迟：按汇报场景的页序参考（例如方案评审该按什么顺序讲），等有了真实 deck 再从里面总结。

## 12. 待补充输入

- 用户的品牌 / 母版文件：决定 `styles/default` 的取值，以及是否启用 `master.pptx`。
- 用户在「页面元素」里选了「其他」但未说明，确认后再决定是否新增组件。
