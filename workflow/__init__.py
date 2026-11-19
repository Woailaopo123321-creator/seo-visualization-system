"""
LangGraph 版 SEO 工作流（路线图第 1 阶段：图化工作流 + 真正可暂停的人工审批）

- spec.py   阶段 / 闸门 / 分组定义（单一数据源，UI 与图共用）
- tools.py  可替换的阶段工具接口；当前为示例数据，标注了 MCP / LLM 接入点
- graph.py  StateGraph 构建：确定性流水线 + 并行审计分支 + interrupt() 闸门
- engine.py 运行管理：SqliteSaver 检查点、thread_id、运行列表、恢复
"""

from .engine import WorkflowEngine, WorkflowError

__all__ = ["WorkflowEngine", "WorkflowError"]
