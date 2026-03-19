"""
阶段二 LangGraph 图定义
流程：高阶修改（含循环）→ 低阶逐句修改（含循环）→ 组装 V6
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from phase2.state import Phase2State
from phase2.nodes import (
    generate_v2_node,
    present_v2_node,
    parse_high_order_action_node,
    accept_high_order_node,
    regenerate_high_order_node,
    self_edit_high_order_node,
    split_sentences_node,
    generate_sentence_suggestion_node,
    present_sentence_node,
    accept_sentence_node,
    keep_sentence_node,
    regenerate_sentence_node,
    assemble_v6_node,
    route_high_order,
    route_low_order,
    route_sentence_loop,
)


def build_phase2_graph(checkpointer=None):
    builder = StateGraph(Phase2State)

    # ── 节点 ──────────────────────────────────────────────────
    builder.add_node("generate_v2",                  generate_v2_node)
    builder.add_node("present_v2",                   present_v2_node)
    builder.add_node("parse_high_order_action",      parse_high_order_action_node)
    builder.add_node("accept_high_order",            accept_high_order_node)
    builder.add_node("regenerate_high_order",        regenerate_high_order_node)
    builder.add_node("self_edit_high_order",         self_edit_high_order_node)
    builder.add_node("split_sentences",              split_sentences_node)
    builder.add_node("generate_sentence_suggestion", generate_sentence_suggestion_node)
    builder.add_node("present_sentence",             present_sentence_node)
    builder.add_node("accept_sentence",              accept_sentence_node)
    builder.add_node("keep_sentence",                keep_sentence_node)
    builder.add_node("regenerate_sentence",          regenerate_sentence_node)
    builder.add_node("assemble_v6",                  assemble_v6_node)

    # ── 高阶修改流程 ──────────────────────────────────────────
    builder.add_edge(START, "generate_v2")
    builder.add_edge("generate_v2", "present_v2")
    builder.add_edge("present_v2", "parse_high_order_action")
    builder.add_conditional_edges("parse_high_order_action", route_high_order, {
        "accept_all":      "accept_high_order",
        "request_changes": "regenerate_high_order",
        "self_edit":       "self_edit_high_order",
    })
    builder.add_edge("regenerate_high_order", "present_v2")       # 高阶循环

    # ── 高阶 → 低阶衔接 ───────────────────────────────────────
    builder.add_edge("accept_high_order",    "split_sentences")
    builder.add_edge("self_edit_high_order", "split_sentences")

    # ── 低阶修改流程 ──────────────────────────────────────────
    builder.add_edge("split_sentences", "generate_sentence_suggestion")
    builder.add_edge("generate_sentence_suggestion", "present_sentence")
    builder.add_conditional_edges("present_sentence", route_low_order, {
        "accept":              "accept_sentence",
        "keep_original":       "keep_sentence",
        "request_alternative": "regenerate_sentence",
    })
    builder.add_edge("regenerate_sentence", "present_sentence")   # 低阶单句循环

    # ── 句子循环 / 结束 ───────────────────────────────────────
    builder.add_conditional_edges("accept_sentence", route_sentence_loop, {
        "continue": "generate_sentence_suggestion",
        "done":     "assemble_v6",
    })
    builder.add_conditional_edges("keep_sentence", route_sentence_loop, {
        "continue": "generate_sentence_suggestion",
        "done":     "assemble_v6",
    })

    builder.add_edge("assemble_v6", END)

    return builder.compile(checkpointer=checkpointer)
