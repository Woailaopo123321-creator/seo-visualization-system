# SEO 学习可视化系统

基于 Flask 的 SEO 可视化与多智能体自动化系统，共 54 个页面（6 个分类）+ 一组 JSON API。

本仓库已把「完整优化包」与中文可视化增强相结合：青绿主题与 Noto 中文字体、评分页交互试算、`/api/backlinks/score`，以及旧路径兼容（`/knowledge` → `/seo`，`/workflow` → `/workflow-runs`，`/backlink-anchors` → `/anchor-text`）。

## 功能

- **仪表盘** `/dashboard`：统计卡片、知识看板、工作流阶段、多智能体协作、心理学洞察 —— **数据实时计算**（任务数、完成率、平均进度、Agent 运行次数），看板列可直接「+ 添加任务」
- **学习看板** `/`：任务增删改、拖动进度、◀ ▶ 切换阶段，数据持久化到 `data/learning_data.json`
- **统一界面**：全部 54 个页面继承 `templates/base.html`，共用左侧分组导航（可搜索、当前页高亮）、顶栏、相关页面标签和 `static/app.css` 样式；手机上侧栏收起为 ☰ 抽屉
- **全部页面** `/sitemap`：按分类列出所有页面
- **手机控制台** `/mobile`：移动端导航入口，统计卡片（任务数、平均进度、Agent 完成次数、工作流阶段数）来自真实数据
- **离线快照** `mobile_dashboard_offline.html`：由 `python scripts/export_offline.py` 生成的单文件仪表盘（CSS/JS 内联，可直接双击打开或分享），数据为生成时刻的快照
- **外链分析**：竞品结构、质量评分模型、锚文本分布、四工具流程
- **SEO 知识**：2026 算法、AI Overviews、E-E-A-T、工具对比
- **工作流审批台** `/workflow-runs`（LangGraph）：17 个阶段跑在 LangGraph `StateGraph` 上，SQLite 检查点持久化（每次运行一个 `thread_id`，服务重启后可继续）；4 个必选的**真正暂停**人工闸门（`interrupt()`）：关键词优先级 → 内容简报（可「打回重写」，最多 2 次）→ 发布前确认 → 外链外展（勾选允许外展的域名）；另有 2 个**可选闸门**（查询扇出子问题确认、外链数据工具确认），启动时勾选或用 `SEO_OPTIONAL_GATES` 设默认值；可删除单个运行或「清空全部」演示数据；段落审计 / 引用监控 / 查询扇出三项**并行审计**后汇合。页面显示阶段图、当前阶段、待审批卡片（批准 / 按修改批准 / 拒绝）、审批记录、执行轨迹与运行历史；仪表盘、侧栏、手机页显示待审批数
- **多 AI 架构知识**：`/agent-patterns`（9 种多智能体模式 + 5 个框架对比、记忆、MCP vs A2A、HITL、成本）、`/agent-architecture`（本系统诊断、改造前/后架构图、角色与闸门、阶段 0–5 路线图、哪些能力需要 API 密钥）；来源：[多 AI 自动化架构学习报告](https://cursor.com/canvas/store-782b3932-aad0-4e23-aa38-c09e650912ed/6be012cc-4244-45dd-b295-f8509d775430)
- **智能路由** `POST /api/ai/route`：Supervisor 规则路由，把一句话请求分派到对应 Agent / 页面（不调用 LLM）
- **自动化（旧版）**：SEOWorkflowReAct Agent（17 个阶段一次跑完，保留兼容，返回 `mode: legacy`），E-E-A-T 审计、学习路径分析，均显示 ReAct 轨迹

## 界面细节

- **浅色 / 深色主题**：默认跟随系统（`prefers-color-scheme`），左下角「◐ 自动 / ☀ 浅色 / ☾ 深色」可手动切换并记住；所有颜色走 `static/app.css` 里的 CSS 变量
- **加载 / 空 / 出错状态**：异步区域统一显示转圈、空状态说明、出错原因 + 「重试」按钮；操作结果用右上角（手机在底部）提示消息反馈
- **键盘与读屏**：「跳到正文」链接、清晰的焦点框、当前页 `aria-current`、菜单按钮 `aria-expanded`、按 `/` 聚焦页面搜索、`Esc` 关闭手机抽屉；看板按钮带完整的读屏标签，重新渲染后焦点不丢
- **手机**：触屏按钮与链接 ≥ 44px，390px 宽度下所有页面无横向滚动
- **时间**：数据库统一存 UTC，界面按浏览器本地时区显示并标注（如「2026-11-19 09:46（UTC+8）」）
- **打印**：打印时隐藏侧栏和按钮、强制浅色、展开折叠内容、外部链接附上网址
- **性能**：文本响应 gzip 压缩；静态资源 URL 带版本号并长期缓存

## 快速启动

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python app.py                      # 默认只监听 127.0.0.1:5000
HOST=0.0.0.0 PORT=8000 python app.py   # 需要局域网/手机访问时
gunicorn -w 2 -b 0.0.0.0:5000 app:app  # 生产部署
```

访问 `http://127.0.0.1:5000/dashboard`

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `127.0.0.1` | 监听地址 |
| `PORT` | `5000` | 端口 |
| `FLASK_DEBUG` | `0` | `1` 开启调试（仅本地） |
| `SEO_DATA_FILE` | `data/learning_data.json` | 任务数据 + Agent 运行统计（重启不清零） |
| `SEO_WORKFLOW_DB` | `data/workflow.sqlite` | LangGraph 检查点 + 运行列表（WAL 模式） |
| `SEO_OPTIONAL_GATES` | 空 | 默认开启的可选闸门，逗号分隔：`fanout,tool_select` |
| `SEO_LOGIN_MAX_ATTEMPTS` | `5` | 登录 / 令牌连续失败多少次后锁定 |
| `SEO_LOGIN_LOCKOUT_SECONDS` | `900` | 锁定时长（秒） |
| `SEO_LOG_LEVEL` | `INFO` | 日志级别 |

所有配置都在 `config.py` 里集中读取。
| `SEO_ADMIN_TOKEN` | 未设置 | 管理员令牌，见下方「权限」 |
| `SEO_SECRET_KEY` | 每次启动随机 | 登录会话签名密钥；设置后重启不会掉登录 |

## 权限

修改数据的接口（`POST/PUT/PATCH/DELETE /api/tasks…`、`POST /api/cache/clear`、启动工作流与审批 `POST /api/workflow/runs…`）受保护；浏览页面、读取数据、运行 AI 分析不受限制。

- **未设置 `SEO_ADMIN_TOKEN`（默认）**：只允许本机（127.0.0.1 / ::1）修改，本地使用零配置；其他设备只读（返回 403）。左下角显示「🖥️ 本机模式」。
- **设置了 `SEO_ADMIN_TOKEN`**：所有修改都需要令牌（包括本机），两种方式：
  - 浏览器：左下角「登录」→ 输入令牌（会话 Cookie，HttpOnly + SameSite=Lax）
  - 脚本：请求头 `Authorization: Bearer <令牌>` 或 `X-Admin-Token: <令牌>`
- 所有修改请求还会校验 `Origin`，拒绝跨站请求（防止恶意网页借用浏览器修改本机数据）。
- **防暴力破解**：同一地址登录或请求头令牌连续输错 5 次，锁定 15 分钟（返回 429 + `Retry-After`）；登录成功即清零。计数在内存里，单进程有效。
- ⚠️ 放在 Nginx 等反向代理后面时，所有请求看起来都来自 127.0.0.1，**必须设置 `SEO_ADMIN_TOKEN`**。

```bash
SEO_ADMIN_TOKEN=换成一串长随机字符 SEO_SECRET_KEY=另一串随机字符 HOST=0.0.0.0 python app.py
curl -X POST -H "Authorization: Bearer $SEO_ADMIN_TOKEN" -H "Content-Type: application/json" \
     -d '{"title":"新任务"}' http://127.0.0.1:5000/api/tasks
```

## 测试

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

覆盖：全部页面 200 且继承 base 模板、站内链接无死链、模板与注册表一致、任务 CRUD 与校验、全部 AI 接口、缓存/超时/异常、404 页面、权限（本机/远程/令牌/登录会话/跨站/开放重定向）、Agent 统计重启后保留、手机页真实数据、离线快照自包含；LangGraph 工作流（闸门暂停、批准/修改/拒绝/打回重写及次数上限、审批参数校验、重启后从检查点继续、审批接口权限、旧接口兼容、规则路由、新知识页）。登录限流、可选闸门、删除 / 重置、SQLite 并发、压缩缓存、标题层级与无障碍属性、深色主题样式。当前共 179 个测试。

## 结构

```
app.py              # Flask 主应用（create_app 工厂、API、错误处理、gzip / 缓存头）
config.py           # 集中配置：环境变量、默认路径、日志格式
security.py         # 登录 / 令牌失败计数与锁定
pages.py            # 页面注册表：路由 / 导航 / 站点地图的唯一数据源
store.py            # 任务存储：线程锁 + 原子写入 + 字段校验
agents/             # ReAct Agent 与协调器（缓存、超时、运行统计）；router.py 为 Supervisor 规则路由
workflow/spec.py    # 阶段、阶段分组、并行审计、人工闸门定义（唯一数据源）
workflow/tools.py   # 阶段工具接口（StageTool），当前为示例数据；标注 MCP / LLM 接入点
workflow/graph.py   # LangGraph StateGraph：阶段节点 + interrupt 闸门 + 并行审计
workflow/engine.py  # WorkflowEngine：SqliteSaver 检查点（WAL、每线程连接、按运行加锁）、运行列表、视图、审批校验与恢复、删除 / 重置
data/dashboard.json # 仪表盘配置（工作流阶段、智能体、心理学指标）
templates/          # base.html 为统一布局；其余页面 {% extends "base.html" %}；error.html / login.html
static/             # app.css（统一样式 + 深色主题 + 打印）、common.js（请求 / 提示消息 / 状态 / 时间 / 主题 / 导航）、favicon.svg
scripts/export_offline.py  # 生成离线仪表盘快照
tests/              # pytest
```

新增页面：在 `pages.py` 的 `PAGES` 中加一行，然后创建模板：

```html
{% extends "base.html" %}
{% block title %}页面标题{% endblock %}
{% block heading %}页面大标题{% endblock %}
{% block related %}<a href="/seo">SEO</a>{% endblock %}   {# 可选：相关页面标签 #}
{% block head %}<style>/* 页面专属样式 */</style>{% endblock %}
{% block content %}<div class="container"><div class="card">…</div></div>{% endblock %}
```

## API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 健康检查、Agent 统计、缓存大小、运行时长 |
| GET | `/api/dashboard` | 仪表盘全部数据 |
| GET | `/api/pages` | 分组页面列表 |
| GET / POST | `/login` · `/logout` | 管理员登录 / 退出（仅设置令牌时需要） |
| GET / POST | `/api/tasks` | 任务列表 / 新建（`title` 必填 ≤80 字，`status`、`priority`、`progress` 0-100 可选） |
| PUT / PATCH / DELETE | `/api/tasks/<id>` | 更新 / 删除任务 |
| GET | `/api/tasks/stats` | 任务统计 |
| POST | `/api/ai/analyze` · `/api/ai/react` · `/api/ai/analyze-react` | 进度分析（普通 / ReAct） |
| POST | `/api/ai/seo-path` · `/api/ai/eeat-audit` · `/api/ai/seo-workflow` | ReAct Agent（workflow 支持 `site`、`topic`） |
| POST | `/api/ai/mindmap` · `/api/ai/recommend` | 思维导图（`topic`）/ 推荐（`context`: general/complex/planning） |
| POST | `/api/cache/clear` | 清空 Agent 结果缓存 |
| GET | `/api/workflow/graph` | 阶段 / 闸门定义、工具类型、Mermaid 图 |
| GET / POST 🔒 | `/api/workflow/runs` | 运行列表与计数 / 启动新运行（`site`、`topic`、可选 `optional_gates`，返回 201，停在第一个闸门） |
| DELETE 🔒 | `/api/workflow/runs/<thread_id>` | 删除一次运行（检查点 + 审批记录） |
| POST 🔒 | `/api/workflow/reset` | 清空全部运行（需 `{"confirm": true}`） |
| GET | `/api/workflow/runs/<thread_id>` | 运行状态：阶段进度、待审批内容、审批记录、轨迹、产出 |
| POST 🔒 | `/api/workflow/runs/<thread_id>/resume` | 审批并继续：`{"action": "approve / edit / reject", "gate": "…", "comment": "…", "edits": {…}}`；edits 按闸门：`priority_keywords`、`title`/`outline`、`subquestions`、`tool`、`approved_targets`；闸门不匹配或无待审批 409 |
| POST | `/api/ai/route` | 规则路由（`query`），只返回去向，不会启动工作流 |

参数错误返回 400 + 中文错误信息；未登录 401、无权限 403、认证失败过多 429；Agent 失败 500、超时 504。🔒 = 需要写权限的接口：tasks 的 POST/PUT/PATCH/DELETE、cache/clear、workflow 启动 / 审批 / 删除 / 重置。

## 外链质量评分模型

相关性 30% + 编辑性 20% + 流量 15% + 锚文本 15% + 权威 10% + 邻里 10%

阈值 0.70，所有外展需 HITL 人工确认。

## 接入真实工具（预留接口）

工作流的每个阶段通过 `workflow/tools.py` 的工具注册表取工具，替换只需一行，图和界面不用改：

```python
from workflow.tools import FunctionTool, register_tool
register_tool("benchmark", FunctionTool("benchmark", my_search_console_fn, kind="mcp"))
```

`fn(site=..., topic=..., state=...)` 返回 dict。阶段定义里 `plug="MCP"` 表示适合接 MCP 数据源（Search Console、页面抓取、外链数据），`plug="LLM"` 表示需要模型（目前只有内容简报）。

> 说明：各 Agent 与工作流阶段的结果目前仍为内置示例数据（模拟），未接入真实 SEO 工具或 LLM（需要 API 密钥）。
