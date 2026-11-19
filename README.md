# SEO 学习可视化系统

基于 Flask 的 SEO 学习可视化。外链质量分和自动化轨迹由 `agents/` 里的评分模型与 ReAct 工作流计算；没有真实采集的图表会在页面上标明 **示例数据**。

## 功能

- **概览** `/dashboard`：阈值、工作流阶段、多智能体协作、心理学洞察、示例候选图表、各页面入口、示例知识看板
- **手机控制台** `/mobile`：移动端入口，链到全部页面
- **竞品结构** `/backlink-competitor`：引用域、外链类型、差距汇总
- **评分模型** `/backlink-score-model`：六维加权、0.70 阈值、滑块试算、示例候选
- **锚文本** `/backlink-anchors`：类型分布与自然度
- **四工具流程** `/backlink-tools`：研究 → 差距 → 评分 → 验证，以及外部工具建议
- **SEO 知识** `/knowledge`：2026 算法笔记、AI Overviews、E-E-A-T、工具对比（中文笔记）
- **自动化** `/workflow`：`SEOWorkflowReAct` 示例运行的思考、行动、观察
- **健康检查** `/health`

达到 0.70 的目标进入外展候选，发出前仍要人工确认（HITL）。

## 快速启动

```bash
pip install -r requirements.txt
python app.py
```

访问 `http://127.0.0.1:5000/dashboard`。

测试：

```bash
pytest
```

生产进程可以用 `gunicorn -w 2 -b 0.0.0.0:5000 app:app`。图表使用 Chart.js CDN，不需要前端构建。

## 结构

```
app.py                     # 入口，调用 create_app
seo_app/
  __init__.py              # 应用工厂、错误页、/health
  config.py                # 默认配置与测试配置
  navigation.py            # 侧栏和手机控制台共用的导航
  sample_data.py           # 标明为示例数据的学习数据
  services.py              # 把模型和示例数据组装成 JSON
  blueprints/pages.py      # 页面
  blueprints/api.py        # /api JSON
agents/
  react.py                 # ReAct 基类
  scoring.py               # 外链质量评分
  seo_workflow.py          # 研究 → 差距 → 评分 → 验证
templates/                 # 中文页面
static/css/app.css         # 样式
static/js/                 # 图表与交互
tests/                     # 路由、评分、工作流
```

## 外链质量评分

相关性 30% + 编辑性 20% + 流量 15% + 锚文本 15% + 权威 10% + 邻里 10%。

质量分保留两位小数。阈值 **0.70**。所有外展都需要人工确认，达到阈值只表示可以进入候选。

`POST /api/backlinks/score`，请求体：

```json
{"features": {"topical_relevance": 0.85, "editorial_placement": 0.78, "real_traffic": 0.62, "anchor_naturalness": 0.88, "authority_score": 0.70, "link_neighborhood": 0.75}}
```

每个维度都是 0 到 1 之间的数字。

## 接口

| 方法 | 路径 | 内容 |
| --- | --- | --- |
| GET | `/health` | `{"status": "ok"}` |
| GET | `/api/dashboard` | 概览数字和图表 |
| GET | `/api/backlinks/competitors` | 竞品结构与差距 |
| GET | `/api/backlinks/scoring` | 权重、示例候选和默认分数 |
| POST | `/api/backlinks/score` | 按提交的特征计算质量分 |
| GET | `/api/backlinks/anchors` | 锚文本分布 |
| GET | `/api/backlinks/tools` | 四阶段观察和外部工具建议 |
| GET | `/api/knowledge` | 学习笔记与对比图 |
| GET | `/api/workflow` | 一次示例运行的步骤和得分构成 |

JSON 中的中文不会转成 `\uXXXX`。工作流工具里的发现数、差距数和验证数是内置示例观察；质量分是模型算出来的。
