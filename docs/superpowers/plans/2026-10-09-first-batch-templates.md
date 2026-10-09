# 首批模板编写说明

日期：2026-10-09
范围：22 个新模板（清单见第 3 节），全部使用现有布局元素（`text` / `bullets` / `shape` / `grid`）和组件（`layered-arch` / `table` / `block-diagram`），不新增组件、不改 `src/` 和 `styles/`。

## 1. 开始前必读

- `AGENTS.md`：仓库规则，尤其是「结构约定」和「新增一个模板」。
- 参考模板：`templates/system/solution-layered-arch/`（`template.yaml`、`example.yaml`、`preview.png`）。新模板的写法、注释风格、槽位描述方式都照它来。
- 可用的颜色和文字样式 token：`styles/default/style.yaml`。
- 组件的数据结构：`src/ppt_templates/components/` 下各文件的 `SCHEMA` 和 `PROPS_SCHEMA`（或 `props_schema`）。

## 2. 统一设计规则

**页框与区域**
- 除封面、章节页用 `frame: none` 外，一律 `frame: standard`。standard 模板的 layout 坐标以 body 区左上角为原点，body 区为 1216×560。
- `frame: none` 时画布 1280×720，四边页边距同样留 32px。
- standard 模板的标题槽位照抄参考模板：`title`（≤14，必填）、`title_suffix`（≤16，可选）、`takeaway`（≤40，可选）。

**字号（只能用 token）**

| 用途 | token |
|---|---|
| 小节标题、重点句、层名 | `emphasis`（14 加粗） |
| 条目名称 | `body_strong`（12 加粗） |
| 正文 | `body`（12） |
| 次要说明 | `detail`（10，muted） |
| 图例、注释 | `caption`（9） |
| 指标数值 | `kpi`（24 加粗） |
| 封面 / 章节页的大标题 | `title`（24）+ `title_suffix`（18），可用 `color: on_primary` 放在深色底上 |

**颜色（只能用 token）**
- `primary`：小节标题文字、深色块。
- `accent`：强调竖条、指标数值。
- `surface`：卡片底色。
- `highlight` / `highlight_strong`：本次新增、推荐方案、我们的选择。
- `muted`：次要文字。
- `line`：分隔线。

**版面**
- 内容铺满 body 区，避免大片空白；同一页内的元素左右边缘对齐。
- 栏间距统一 24px；卡片内边距 12–16px；条目之间 8–12px。
- 卡片样式统一为 `surface` 底，左侧或顶部 4px 的 `accent` 强调条，与参考模板一致。

**字数上限（maxLength）怎么估**
- 每个中文字约等于字号的像素宽度：`body` 16px、`emphasis` 18.7px、`detail` 13.3px、`kpi` 32px。
- 行高按字号 × 1.2 估算。
- 先按框的宽高算出能放几行几个字，再留出约 10% 余量。

**数据里的序号**：布局无法自动编号，需要序号的地方（目录、章节）把序号作为槽位字段（如 `no: "01"`）。

**示例内容（example.yaml）**
- 用真实感强的业务内容，领域是 AI 训练集群、存储系统、服务器硬件、系统软件。
- 中文和数字之间不加空格（如「缩短70%」「2026年9月」），中文和英文单词之间可以留空格。
- 示例要把每个槽位都填上，并尽量接近字数上限，用来暴露溢出问题。

**元数据**
- `when_to_use` 一句话说明用途；`when_not_to_use` 写最容易混淆的替代模板。
- 数量和长度只写在 `slots` 里，不在说明文字里重复。
- 适用于其他主题时写 `also_fits`。

## 3. 模板清单与内容结构

下面只写用途、槽位要点和布局草图，具体坐标和字数上限由编写者按第 2 节的规则确定。目录名就是 `<主页功能>-<形态>`，与 id 的后半段一致。

### A 组：common（结构与总结）

1. `common.cover-basic`，roles `[cover]`，`frame: none`。封面：`title`（主标题）、`subtitle`、`presenter`（汇报人 / 部门）、`date`。左侧约 45% 宽的 `primary` 深色块放标题和副标题（`on_primary` 文字），右侧留白配一条 `accent` 竖条；汇报人和日期放在左下。
2. `common.agenda-list`，roles `[agenda]`。目录：`items` 3–6 项 `{no, name, note}`。单列 grid，每行左侧是 `no`（`kpi` 样式、`accent` 色），右侧是名称（`emphasis`）加一行说明（`detail`）。
3. `common.section-basic`，roles `[section]`，`frame: none`。章节页：`no`、`title`、`subtitle`。整页 `primary` 底，大号序号加标题，下方一条 `accent` 短横线。
4. `common.summary-points`，roles `[summary]`。要点总结：`points` 3–6 项（`bullets`，对象数组 `{text, level}`，level 为 0–1 的整数）；`conclusion`（一句结论，放在页面底部的 `highlight` 底横条里，用 `emphasis`）。
5. `common.summary-kpi`，roles `[summary, result]`，tags 含「测试结果」。关键数字：`kpis` 2–4 项 `{value, label, note}`，上方一排大指标卡；`notes` 2–4 条（`bullets`），放在下方解释这些数字。

### B 组：common（表格与收尾）

6. `common.overview-table`，roles `[overview, benchmark]`。通用对比表格：`matrix`（`table` 组件，可设 `highlight_column`）铺满大部分 body；底部一行 `note`（`detail`）写数据口径或结论。
7. `common.ask-decision`，roles `[ask]`。决策请求 / 资源诉求：左栏 `context`（2–3 条 bullets，说明为什么要决策）；右栏 `asks` 1–3 项 `{item, detail}` 做成 `highlight` 卡片；底部 `deadline`（`detail`，可选）。
8. `common.risk-table`，roles `[risk]`。风险与应对：`risks` 2–6 项 `{risk, level, mitigation, owner}`，level 为「高 / 中 / 低」（enum）。用 grid 做成表格行，表头用 `value` 固定文字，表头行用 `primary` 底、`on_primary` 字。
9. `common.next-list`，roles `[next]`。下一步计划：`items` 2–6 项 `{task, owner, due}`，表格行样式与 risk-table 一致；右侧或底部可选 `support`（需要的支持，`emphasis`）。

### C 组：system / hardware

10. `system.problem-bottleneck`，roles `[problem, analysis]`。系统瓶颈：左栏 `metrics` 2–3 个量化指标卡（`value` 用 `kpi`，但颜色改为 `highlight_strong`，表示问题）；右栏 `causes` 2–4 项 `{name, detail}` 根因卡片；顶部一句 `symptom`（`emphasis`，现象描述）。
11. `system.roadmap-stages`，roles `[roadmap]`，also_fits `[product, hardware, software]`。演进路线：`stages` 3–5 项 `{period, name, points: [字符串，最多 3 条]}`。中间一条横贯的 `line` 细线做时间轴，grid 每列一个阶段：时间（`body_strong`，`accent`）、阶段名（`emphasis`）、要点（`bullets` 或多段 `detail`）。
12. `hardware.solution-block-diagram`，roles `[solution]`，level `system`。硬件框图：左侧约 760 宽放 `diagram`（`block-diagram` 组件）；右侧 `params` 3–6 项 `{name, value}` 关键参数（名称 `detail`，数值 `body_strong`），下方 `notes` 1–3 条说明。
13. `hardware.selection-matrix`，roles `[selection, benchmark]`。选型对比：左侧约 800 宽放 `matrix`（`table`，用 `highlight_column` 标推荐方案）；右侧推荐卡片 `recommendation {choice, reasons: [2–3 条]}`，`highlight` 底。

### D 组：software / project

14. `software.problem-pain-points`，roles `[problem]`。实现问题：`points` 正好 3 项（minItems = maxItems = 3）`{name, detail, impact}`，三栏卡片；`impact` 是量化影响，用 `kpi` 配 `highlight_strong`。
15. `software.solution-module-flow`，roles `[solution]`，level `module`。模块方案：左侧 `flow`（`block-diagram`，展示处理流程，高亮新增节点）；右侧 `design_points` 2–3 项，写法同参考模板的「关键设计」。
16. `software.result-before-after`，roles `[result]`，also_fits `[system, hardware]`。改进前后：`metrics` 2–4 项 `{name, before, after, delta}`，每项一行：名称 | 改进前（`muted`） | 箭头或分隔 | 改进后（`accent` 加粗） | 提升幅度（`kpi`）；底部可选 `summary`（`emphasis`）。
17. `project.overview-milestones`，roles `[overview]`。里程碑进展：`milestones` 3–6 项 `{date, name, status}`，status 为「已完成 / 进行中 / 未开始」（enum）；时间轴写法同 roadmap-stages；下方 `notes` 1–3 条（`bullets`）写当前进展和问题。

### E 组：trend / competition / workload / model / product

18. `trend.trend-points`，roles `[trend]`。趋势要点：`trends` 3–4 项 `{name, evidence, impact}`，每列一张卡片，上半部分写趋势和依据，下半部分是「对我们的影响」（`highlight` 底）。
19. `competition.overview-landscape`，roles `[overview, benchmark]`。竞争格局：`players` 3–6 项 `{name, position, strength, weakness}` 做成 grid 卡片（2–3 列）；底部一句 `insight`（`emphasis`）。
20. `workload.requirement-matrix`，roles `[requirement, analysis]`，also_fits `[system, hardware]`。负载需求：`items` 3–6 项 `{feature, value, requirement}`，每行：负载特征 | 量化值（`body_strong`，`accent`）| 箭头 | 对系统的需求；顶部 `workload`（负载名称，`emphasis`）。
21. `model.overview-structure`，roles `[overview]`，also_fits `[workload]`。模型结构：左侧 `diagram`（`block-diagram`，展示模型结构）；右侧 `specs` 3–6 项 `{name, value}`（参数量、层数、上下文长度等），下方 `notes` 1–3 条。
22. `product.overview-sandbox`，roles `[overview]`。业务沙盘：`matrix`（`table`）中行是客户 / 场景，列是产品，单元格写覆盖状态；右侧或底部 `insights` 2–3 条（`bullets`）。

## 4. 每个模板的完成标准

1. `templates/<topic>/<目录名>/` 下有 `template.yaml`、`example.yaml`、`preview.png`。
2. `uv run ppt validate` 对本模板没有任何错误。多人并行编写时，可以忽略其他模板目录的报错和「catalog.json 不是最新的」。
3. `uv run ppt preview <id> --write` 生成预览后，用 Read 工具查看：
   - 没有文字溢出、重叠、被裁切；
   - 元素对齐；
   - 没有大片空白；
   - 风格与参考模板一致。

   有问题就调整坐标或字数上限后重新预览，最多迭代 3 轮。

## 5. 收尾（由协调者完成）

- `uv run ppt catalog`、`uv run pytest -q`、`uv run ppt validate` 全部通过。
- 把所有模板的 example 拼成一份演示 deck，渲染为 `out/first-batch.pptx`，给用户整体查看。
- 一次提交。
