# 多模型适配计划

日期：2026-10-09
对应 spec 第 8 节。目标：Claude Code、Codex、Cursor、Gemini CLI 能通过 skill 使用模板库，MCP 客户端能通过 MCP server 使用，几种方式走同一套 CLI 和同一套函数。

## 各家读取方式（已核实）

| 工具 | 仓库规则 | Skill |
|---|---|---|
| Codex | 读 `AGENTS.md` | 读 `.agents/skills/` |
| Cursor | 读 `AGENTS.md` | 读 `.agents/skills/`，同时也扫描 `.claude/skills/` |
| Gemini CLI | 默认读 `GEMINI.md`，需配置才读 `AGENTS.md` | 读 `.agents/skills/` |
| Claude Code | 读 `CLAUDE.md`（已通过 `@AGENTS.md` 引用） | 只读 `.claude/skills/`；软链目录的发现时好时坏 |

**结论**
- skill 的正本放在 `.agents/skills/ppt-templates/SKILL.md`。
- `.claude/skills/ppt-templates/SKILL.md` 放一份真实副本，不用软链。由 `ppt sync-skill` 从正本复制过去，`ppt validate` 检查两者完全一致。
- Cursor 可能把同名 skill 列出两次，内容相同，可以接受。

## 任务

### 1. SKILL.md（正本）

`.agents/skills/ppt-templates/SKILL.md` 遵循 Agent Skills 格式。

**frontmatter**
- `name: ppt-templates`，必须与目录名一致，只用小写字母、数字和连字符，最长 64 个字符。
- `description` 不超过 1024 个字符，写清楚什么时候用：用户要做汇报 PPT / 幻灯片 / 某一页的版式时，用本仓库的页模板生成原生 `.pptx`。

**正文**（控制在 150 行内，不复制任何模板内容）
- 先确认当前目录是仓库根目录（含 `taxonomy.yaml`），所有命令都用 `uv run ppt ...` 运行。
- 流程：
  1. 按需求排出页功能顺序；`taxonomy.yaml` 的 `roles` 里有每个页功能要回答的问题。
  2. 读 `catalog.json` 或运行 `uv run ppt list [--topic/--role/--density/--tag]`，为每一页挑模板，可以跨主题。
  3. 对每个选中的模板运行 `uv run ppt show <id>`，读 `slots`、`guidance` 和示例。
  4. 写 `deck.yaml`（附一个最小示例）。
  5. 运行 `uv run ppt validate deck.yaml`，按中文报错修改，例如超字数就精简。
  6. 运行 `uv run ppt render deck.yaml -o out/<名字>.pptx`。
  7. 运行 `uv run ppt preview deck.yaml -o out/<名字>-preview/`，查看 PNG，有溢出或空洞就回到第 4 步。
- 规则：
  - 每页只用一个模板，内容只填 `slots` 里定义的字段。
  - 字体和字号由风格统一决定，不要试图修改。
  - 只做中文，中文和数字之间不加空格。
  - 可选字段可以省略。
  - 序号类字段写成字符串（如 `"01"`）。
- 最后一行注明：MCP 客户端可以改用 `ppt mcp` 提供的工具，流程相同。

### 2. Claude Code 副本与同步命令

- 新增 `ppt sync-skill`：把正本复制到 `.claude/skills/ppt-templates/SKILL.md`。目标列表写成常量，方便以后加别的工具。
- 新增仓库校验：
  - 正本存在；
  - frontmatter 合法（`name` 与目录名一致且符合格式，`description` 非空且不超过 1024 字）；
  - 每个副本与正本逐字节一致，否则报 `… 与正本不一致（运行 uv run ppt sync-skill）`。
- 对应的测试。

### 3. Gemini CLI

`.gemini/settings.json`：

```json
{"context": {"fileName": ["AGENTS.md"]}}
```

### 4. MCP server

- 依赖：`uv add mcp`，使用官方 Python SDK 的 `FastMCP`。
- 新模块 `src/ppt_templates/mcp_server.py`，CLI 新增 `ppt mcp`，以 stdio 方式运行。
- 工具（中文描述；内部复用现有函数，不重复实现）：
  - `get_taxonomy()`：返回主题和页功能（含 `question`）。
  - `list_templates(topic=None, role=None, density=None, tag=None)`：返回 catalog 条目，`topic` 同时匹配 `also_fits`。
  - `get_template(template_id)`：返回元数据、`slots`、`guidance`、`example`。不返回 `layout`，因为写内容用不到，还占 token。
  - `validate_deck(deck)`：返回 `{"ok": bool, "errors": [中文错误]}`，包括风格是否存在。
  - `render_deck(deck, filename="deck.pptx")`：只写入仓库的 `out/` 目录；`filename` 必须是不含路径分隔符、以 `.pptx` 结尾的文件名；返回绝对路径。先校验，失败就报错。
  - `preview_deck(deck)`：渲染后把每页转成 PNG（宽 1280），以 MCP 图片内容返回；本机没有 `soffice` 时给出清楚的中文错误。
- 测试：
  - 直接调用各工具函数；
  - 用 SDK 的内存连接（`mcp.shared.memory.create_connected_server_and_client_session` 或等价方式）做一次 `list_tools` 和 `call_tool` 的冒烟测试；
  - `render_deck` 拒绝 `../x.pptx`、`a/b.pptx`、`x.txt`。
- 仓库根目录加 `.mcp.json`，供 Claude Code 按项目加载：

```json
{"mcpServers": {"ppt-templates": {"command": "uv", "args": ["run", "ppt", "mcp"]}}}
```

### 5. 文档

- `AGENTS.md`：
  - 更新「当前状态」和「命令」（加入 `ppt mcp`、`ppt sync-skill`）。
  - 新增「MCP」小节，给出 Claude Desktop 等客户端的配置示例：`"command": "uv", "args": ["--directory", "<仓库绝对路径>", "run", "ppt", "mcp"]`。
  - 「Skill 与多模型适配」一节改为「真实副本 + sync-skill」的说法。
- spec 第 8.1 节：软链方案改为副本方案，写明原因（Claude Code 只读 `.claude/skills`，对软链的发现不稳定）；第 8.2 节补上 `get_taxonomy`、`preview_deck` 两个工具和 `render_deck` 的写入限制。

## 完成标准

- `uv run pytest -q` 全部通过，`uv run ppt validate` 通过。
- `uv run ppt mcp` 能启动；冒烟测试证明可以列出和调用工具。
- 提交到 main，提交信息末尾带 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`。
