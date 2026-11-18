# SEO 学习可视化系统

基于 Flask 的 SEO 可视化与多智能体自动化系统。

## 功能

- **仪表盘** `/dashboard`：系统概览、知识看板、工作流阶段、多智能体协作、心理学洞察
- **手机控制台** `/mobile`：移动端导航入口
- **外链分析**：竞品结构、质量评分模型、锚文本分布、四工具流程
- **SEO 知识**：2026 算法、AI Overviews、E-E-A-T、工具对比
- **自动化**：SEOWorkflowReAct Agent，含研究 → 差距 → 评分 → 验证流程

## 快速启动

```bash
pip install -r requirements.txt
python app.py
```

访问 `http://127.0.0.1:5000/dashboard`

## 结构

```
app.py              # Flask 主应用
agents/             # ReAct Agent 实现
templates/          # 可视化页面
static/             # CSS
```

## 外链质量评分模型

相关性 30% + 编辑性 20% + 流量 15% + 锚文本 15% + 权威 10% + 邻里 10%

阈值 0.70，所有外展需 HITL 人工确认。
