"""
阶段一 LangGraph 图定义
流程：START → cet_scoring → six_dim → format_report → END
"""

from langgraph.graph import StateGraph, START, END

from phase1.state import Phase1State
from phase1.nodes import cet_scoring_node, six_dim_node, format_report_node


def build_phase1_graph():
    """构建并编译阶段一评分图。"""
    builder = StateGraph(Phase1State)

    # 添加节点
    builder.add_node("cet_scoring", cet_scoring_node)
    builder.add_node("six_dim", six_dim_node)
    builder.add_node("format_report", format_report_node)

    # 添加边（顺序执行）
    builder.add_edge(START, "cet_scoring")
    builder.add_edge("cet_scoring", "six_dim")
    builder.add_edge("six_dim", "format_report")
    builder.add_edge("format_report", END)

    return builder.compile()


# 导出编译好的图（直接 import 使用）
phase1_graph = build_phase1_graph()
