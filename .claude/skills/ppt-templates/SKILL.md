---
name: ppt-templates
description: "用本仓库的页模板生成原生 .pptx。当用户要做汇报 PPT、幻灯片、评审材料，或需要某一页的版式（封面、趋势、竞争格局、问题分析、方案架构、选型对比、效果收益、规划、总结、决策请求等）时使用：先按需求排出页功能顺序，再从模板库为每页挑模板（可跨主题），按模板的 slots 写出 deck.yaml，经校验后渲染为 .pptx 并生成预览图检查排版。只支持中文。"
---

# 用页模板生成 PPT

页粒度的模板库：每个模板是一页的版式加内容契约，`deck.yaml` 选定风格并按顺序列出页，渲染器统一输出原生 `.pptx`。本 skill 只描述流程，模板内容以仓库为准。

## 准备

- 确认当前目录是仓库根目录，即含 `taxonomy.yaml` 的目录；不是的话先 `cd` 过去。
- 所有命令都用 `uv run ppt ...` 运行。第一次使用先 `uv sync`。
- **LibreOffice（`soffice`）是必需依赖**：第 7 步的预览靠它出图。开始前先检查 `uv run ppt preview common.cover-basic -o out/env-check`，生成了 PNG 就是装好了；报「找不到 soffice」就先安装：
  - Windows：`winget install --id TheDocumentFoundation.LibreOffice -e`（装到默认位置即可，`ppt` 会自己找到，不用改 PATH）
  - macOS：`brew install --cask libreoffice`
  - Linux：用发行版的包管理器装，如 `sudo apt install libreoffice-impress`

  安装会改动系统：按所在环境的规则先告诉用户、得到同意后再装；装不了就停下来说明原因。不能因为没装就跳过预览直接交付 `.pptx`。

## 流程

1. **排页功能顺序。** 按用户的需求排出每一页要回答什么问题。`taxonomy.yaml` 的 `roles` 列出所有页功能，`question` 是该页要回答的问题（problem、analysis、selection、solution、result、roadmap……），`topics` 是模板的主题分类。
2. **为每一页挑模板。** 读 `catalog.json`，或运行：

   ```
   uv run ppt list [--topic T] [--role R] [--density D] [--tag X]
   ```

   `--topic` 同时匹配模板声明的 `also_fits`，可以跨主题挑。看 `when_to_use` 判断是否合适；`talk` 是现场讲的稀疏页，`read` 是供阅读的信息密集页。
3. **读模板定义。** 对每个选中的模板运行 `uv run ppt show <id>`，读 `slots`（字段、必填、长度、数量上限）、`guidance`（写作要点）和示例。
4. **写 `deck.yaml`。** 每页 `template` 填模板 id，`data` 按 `slots` 填内容：

   ```yaml
   style: default
   pages:
     - template: common.cover-basic
       data:
         title: 新一代存储系统方案
         subtitle: 2026年第四季度技术评审
         presenter: 存储系统部　张明
         date: 2026年10月
   ```

   其余页同理，按顺序追加到 `pages`。
5. **校验。** `uv run ppt validate deck.yaml`。报错格式是 `<页>  <JSON Pointer>  <消息>`，按消息修改：超字数就精简文字，超数量就合并或删减条目，缺必填字段就补上。
6. **渲染。** `uv run ppt render deck.yaml -o out/<名字>.pptx`。
7. **预览（必做）。** `uv run ppt preview deck.yaml -o out/<名字>-preview/`，逐页查看 PNG。有文字溢出、留白过大或内容空洞，就回到第 4 步调整内容。

## 规则

- 每页只用一个模板，内容只填该模板 `slots` 里定义的字段，不要自己加字段。
- 字体和字号由风格统一决定，不要试图修改；不要往 `deck.yaml` 里写颜色、字体、坐标。
- 只做中文：中文和数字之间不加空格（写 `3.2倍`、`18分钟`）。
- 可选字段没有内容就省略，不要写空字符串或占位文字。
- 序号类字段写成字符串，如 `"01"`，否则 YAML 会把它当成数字。
- 图片槽位（模板里描述为图片路径的字符串）填图片文件的路径，相对 `deck.yaml` 所在目录，支持 png / jpg / gif / bmp / tiff；不填则渲染为带引导文字的占位框。经 MCP 调用时路径相对仓库根目录，且只能引用仓库内的文件。

## 其他调用方式

MCP 客户端可以改用 `uv run ppt mcp` 提供的工具（`get_taxonomy`、`list_templates`、`get_template`、`validate_deck`、`render_deck`、`preview_deck`），流程相同。
