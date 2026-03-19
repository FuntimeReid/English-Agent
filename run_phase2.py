"""
阶段二运行入口
用法：python run_phase2.py

接收阶段一的输出，驱动高阶修改 + 低阶修改的完整交互流程。
"""

import json
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from phase2.graph import build_phase2_graph

# ============================================================
# 示例（直接运行时使用，实际使用时由 run_phase1 提供）
# ============================================================
SAMPLE_TOPIC = """For this part, you are allowed 30 minutes to write a short essay entitled Should the University Campus Be Open to Tourists?"""

SAMPLE_ESSAY = """Nowadays, most of the universities are open to the public. And the famous universities are gradually becoming the new tourism attractions. So a question arise. Should the university campus be open to tourists? People have different opinions.
Some people think that the university campus symblize the literature of the country. The visit to university campuses can give the tourists a general idea of the literature of the country. But other people think that if the university campus are open to tourists, the peace envirnment for the university students to study will be ruined. University campus is the holy place for studying, So they shouldn't be open to tourists.
I think both ideas have its own reasons and the best answer to the question is that the university campus can be open to tourists on Saturday and Sunday or limit the amount of the tourists. In this way, not only the tourists can visit the famous university campuses but also won't the peace environment of the campuses be destroyed.
"""

SAMPLE_PHASE1_BACKEND = {
    "dimensions": {
        "argumentation": {
            "weaknesses": "中心论点不够清晰，论据支撑不足，缺乏具体例证，段落主题句不明确。"
        },
        "discourse": {
            "weaknesses": "段落间过渡生硬，衔接词使用单一，整体结构缺乏层次感。"
        }
    }
}


# ============================================================
# 核心函数
# ============================================================
def run_phase2(
    essay: str,
    topic: str,
    phase1_backend_data: dict,
    thread_id: str = "default",
):
    """
    运行阶段二修改流程。

    参数：
        essay:               V1 原始作文（来自阶段一输入）
        topic:               作文题目
        phase1_backend_data: run_phase1() 返回的 backend_data 字段
        thread_id:           LangGraph checkpointer 线程 ID

    返回：
        (graph, config) 元组，供调用方驱动 interrupt-resume 循环
    """
    checkpointer = MemorySaver()
    graph = build_phase2_graph(checkpointer=checkpointer)
    graph_config = {"configurable": {"thread_id": thread_id}}

    dims = phase1_backend_data.get("dimensions", {})
    initial_state = {
        "essay": essay,
        "topic": topic,
        "argumentation_weaknesses": dims.get("argumentation", {}).get("weaknesses", ""),
        "discourse_weaknesses":     dims.get("discourse", {}).get("weaknesses", ""),
        "phase1_backend_data":      phase1_backend_data,
        "v2_draft":                 None,
        "high_order_history":       [],
        "high_order_iteration":     0,
        "high_order_student_input": None,
        "high_order_action":        None,
        "v4_essay":                 None,
        "v4_sentences":             None,
        "current_sentence_index":   0,
        "sentence_decisions":       [],
        "current_ai_suggestion":    None,
        "current_revision_type":    None,
        "current_low_order_action": None,
        "low_order_iteration_count": 0,
        "v6_essay":                 None,
        "revision_events":          [],
        "phase2_complete":          False,
    }

    # 首次调用，运行至第一个 interrupt
    result = graph.invoke(initial_state, config=graph_config)
    return graph, graph_config, result


# ============================================================
# CLI 交互循环
# ============================================================
def main():
    print("=" * 60)
    print("          阶段二：智能体批阅")
    print("=" * 60)
    print()

    graph, graph_config, result = run_phase2(
        essay=SAMPLE_ESSAY,
        topic=SAMPLE_TOPIC,
        phase1_backend_data=SAMPLE_PHASE1_BACKEND,
    )

    # interrupt-resume 循环
    while not result.get("phase2_complete", False):
        interrupts = result.get("__interrupt__", [])
        if not interrupts:
            break

        # 展示 AI 提示
        prompt_text = interrupts[0].value
        print("\n" + "-" * 60)
        print(prompt_text)
        print("-" * 60)

        # 收集学生输入
        student_input = input("\n你的回复：").strip()
        if not student_input:
            student_input = "接受"

        # 继续执行
        result = graph.invoke(Command(resume=student_input), config=graph_config)

    # 输出最终结果
    print("\n" + "=" * 60)
    print("          修改完成")
    print("=" * 60)
    print(f"\n【V6 最终作文】\n\n{result.get('v6_essay', '')}")

    events = result.get("revision_events", [])
    print(f"\n【阶段三记录】共 {len(events)} 条修改事件")

    # 保存结果
    output = {
        "v1_essay":       SAMPLE_ESSAY,
        "v4_essay":       result.get("v4_essay"),
        "v6_essay":       result.get("v6_essay"),
        "revision_events": events,
    }
    with open("phase2_result.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n结果已保存至 phase2_result.json")


if __name__ == "__main__":
    main()
