from langgraph.graph import StateGraph, START, END

from phase3.state import Phase3State
from phase3.nodes import compute_stats_node, generate_literacy_report_node


def build_phase3_graph():
    builder = StateGraph(Phase3State)
    builder.add_node("compute_stats",           compute_stats_node)
    builder.add_node("generate_literacy_report", generate_literacy_report_node)
    builder.add_edge(START, "compute_stats")
    builder.add_edge("compute_stats", "generate_literacy_report")
    builder.add_edge("generate_literacy_report", END)
    return builder.compile()
