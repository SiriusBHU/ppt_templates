# AGENTS.md

页粒度的 PPT 模板库，最终产出原生 `.pptx`。所有调用方（Agent CLI、MCP 客户端、人工）走同一条路径：选模板 → 按模板的 JSON Schema 写内容 → 交给唯一的渲染器。完整设计见 `docs/superpowers/specs/2026-10-08-ppt-template-repo-design.md`。

## 当前状态

处于设计阶段：设计 spec 已写好，下面列出的目录和 `ppt` 命令都还没有实现。实现落地后更新本节。

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
  - `frame: standard`：坐标以 body 区左上角为原点，按参考尺寸 1160×500 设计，渲染时缩放到风格的实际 body 区。
  - `frame: none`：坐标以画布左上角为原点。
- 颜色、字体、文字样式只能引用 `style.schema.json` 规定的 token，不能写死色值或字体名——否则从不同模板拼出来的 deck 风格会不统一。
- `frame: standard` 的模板由页框渲染 `title` / `takeaway` / `source` 和页码，`layout` 不得再绑定这三个槽位；封面这类整页自由布局的模板用 `frame: none`。
- `slots` 的每个顶层属性都必须被渲染（由页框或恰好一个 `layout` 元素绑定），否则校验报错。`bind` 是点号路径，相对当前作用域解析：顶层是页的 `data`，`grid` 的 `item` 内是当前项，`.` 表示当前项本身。
- 表格、架构图、框图这类复杂元素不在 YAML 里逐个画框，而是引用 `src/ppt_templates/` 中的内置组件（`table`、`layered-arch`、`block-diagram`）。需要新的复杂元素时，新增组件，而不是在模板里堆 shape。
- `catalog.json` 是生成物，改动任何模板后都要重新生成，不要手改。

## 计划中的命令（尚未实现）

Python 3.13 + python-pptx，用 uv 管理环境：

```
uv run ppt list [--topic T] [--role R] [--density D] [--tag X]   # --topic 同时匹配 also_fits
uv run ppt show <id>
uv run ppt validate                 # 校验仓库：模板、风格、taxonomy、catalog 是否最新
uv run ppt validate deck.yaml       # 校验一份 deck 的内容
uv run ppt catalog                  # 重新生成 catalog.json
uv run ppt render deck.yaml -o out.pptx
uv run ppt preview deck.yaml -o dir/     # 每页一张 PNG（soffice → PDF → pypdfium2）
uv run ppt preview <id> --write          # 用 example.yaml 重新生成该模板的 preview.png
uv run ppt mcp                      # 启动 stdio MCP server
uv run pytest                       # 全部测试；找不到 soffice 时跳过预览测试
uv run pytest tests/path::test_name # 单个测试
```

## Skill 与多模型适配

- Skill 的规范位置是 `.agents/skills/ppt-templates/SKILL.md`；`.claude/skills/ppt-templates` 是指向它的软链。只改规范位置。
- SKILL.md 只描述流程（排页功能顺序 → 读 catalog 挑模板 → `ppt show` → 写 deck → validate → render → preview），不要把模板内容复制进去。
- 本文件是仓库规则的规范来源，Codex、Cursor 直接读取；`CLAUDE.md` 只是引用本文件；Gemini CLI 通过 `.gemini/settings.json` 指向本文件。
