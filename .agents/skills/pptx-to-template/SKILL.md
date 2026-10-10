---
name: pptx-to-template
description: "把用户已有的 PPT 页抽象成本仓库的页模板。当用户带来 pptx 样板或用 ppt-skeleton 脱敏的骨架稿，或说「照这页做个模板」「把这些页做成模板」时使用：用 ppt import 读出形状和原图，判断主题、页功能和替换还是新增，按仓库风格约定写 template.yaml 与引导性 example.yaml，再校验、预览、与原图对照，迭代到排版干净。只支持中文。"
---

# 把已有 PPT 页抽象成模板

输入是一份 pptx：可以是用户给的样板，也可以是公司内部真实页经 `tools/ppt-skeleton` 脱敏后带出的骨架稿（随附 `manifest.yaml`）。输出是 `templates/<topic>/<template>/` 下的 `template.yaml`、`example.yaml`、`preview.png`。仓库规则以 `AGENTS.md` 为准，本 skill 只描述流程和踩过的坑。

## 准备

- 在仓库根目录（含 `taxonomy.yaml`）运行 `uv run ppt ...`；第一次先 `uv sync`。导入原图和预览都依赖 LibreOffice（`soffice`）。
- 样板放在 `samples/`（已在 `.gitignore` 里），连同 `manifest.yaml` 一起，永远不要提交。

## 流程

1. **导入。** `uv run ppt import <pptx> [--slide N ...] -o <临时目录>`，每页得到 `original.png` 和 `shapes.yaml`（逻辑像素坐标、最接近的颜色和文字 token、`frame_guess`、图片位的 `suggest: image`）。先看原图理解版式，再从 `shapes.yaml` 取尺寸和比例。
2. **定归属。** 对照 `taxonomy.yaml` 和 `catalog.json`，给每页定主题、页功能（`roles[0]` 决定目录名）和处理方式：替换已有模板、新增，或只给已有模板加 `also_fits`。列成表给用户确认后再动手；真正拿不准的只问一个问题。
3. **拆结构。**
   - 标题：真实页多是一句结论式长标题、没有副标题行 → `frame: standard`，不设 `takeaway` / `title_suffix`，正文自动用 `body_compact`，`title` 上限 36 字左右。
   - 重复结构 → `grid`（可嵌套，序号用 `#`）；「名称：说明」→ `runs`（加粗名称 + 常规说明）。
   - 架构图、路线图、能力地图、表格这类复杂元素 → 先找现有组件；没有就新增组件（照 `src/ppt_templates/components/partitioned_arch.py`：`SCHEMA` 只管结构、`PROPS_SCHEMA`、`check` 与 `render` 共用一个 `_plan`、中文报错、配测试），不要在模板里堆 shape。
   - 图片、图表、截图 → `image` 元素，`placeholder` 写清楚该放什么图。
   - 样板里做不到的手工排法（如同一列上下叠两张卡），取最接近的规整排法，并在汇报里说明。
4. **写模板。**
   - 照 `AGENTS.md` 的风格约定：三色文字、短语加粗句子常规、白底阴影卡片不描边、不画分隔线、16px 节奏、字号只用 token（14 号常规正文用 `lead`）。
   - 保留样板的结构、比例和信息密度；样板的视觉细节（虚线框、灰描边、圆角、浅蓝底等）和风格约定冲突时，以风格约定为准。
   - `maxLength` 按最窄的情况推算：12pt 中文约 16 逻辑像素一个字，14pt 约 18.7，10pt 约 13.3，英文约半个中文宽。条目数不同、可用宽度也不同时，用 JSON Schema 的 `if` / `then` 按数量放宽上限。
   - `example.yaml` 写引导文字（说明这里该填什么），每个字符串用到上限的八成左右；图片槽位留空，让预览显示占位框。绝不能出现样板里的原文、人名、产品名和数字。
5. **校验和对照。** `uv run ppt validate` → `uv run ppt preview <id> --write`，把 `preview.png` 和 `original.png` 并排看，修到没有溢出、重叠、错位，文字填满所在的框。再用一份所有字段都取上限的 deck 做极限测试，并试一次最少条目，看会不会过空。
6. **收尾。** `uv run ppt catalog`、`uv run ppt validate`、`uv run pytest`。把「原图 | 预览」对照图发给用户，列出和样板的差异，以及需要用户拍板的取舍。用户说提交才提交。

## 一次做多页

- 先把多页共同需要的渲染器能力（新元素、新 token、页框变化）单独做完，再每页一个独立子任务并行写模板。
- 并行时只允许一个任务改 `src/` 和 `AGENTS.md`；其余任务只动自己的模板目录、不运行 `ppt catalog`，忽略别的目录尚未完成造成的校验错误。全部完成后统一跑 catalog、validate、pytest。

## 踩过的坑

- `rounded` 的圆角随框的大小变化，大卡片会切到角上的文字 → 卡片用直角。
- `table` 组件字号固定 12 号、单元格左右各留 12px，框窄列多时每格放不下几个字（可放字数 ≈ (框宽 ÷ 列数 − 24) ÷ 16） → 长内容挪到要点里，或在汇报里提出来。
- 行高均分时条目少会显得空 → 合理设 `minItems`，或在汇报里说明。
- 长英文单词放不进窄框会被拦腰折断 → 组件的 `check` 要拦住，示例里少用长英文。
