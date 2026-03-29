"""
阶段三运行入口
用法：python run_phase3.py

接收阶段二的输出，生成写作反馈素养评估报告。
可直接调用 run_phase3()，也可运行 main() 从 phase2_result.json 读取数据。
"""

import json
import os

from phase3.graph import build_phase3_graph


# ============================================================
# 核心函数
# ============================================================
def run_phase3(
    v1_essay: str,
    v6_essay: str,
    topic: str,
    revision_events: list,
    sentence_decisions: list,
    high_order_history: list = None,
) -> dict:
    """
    运行阶段三素养评估流程。

    参数：
        v1_essay:           原始作文（V1）
        v6_essay:           最终修改后作文（V6）
        topic:              作文题目
        revision_events:    阶段二产生的所有修改事件列表
        sentence_decisions: 阶段二产生的逐句决策列表
        high_order_history: 高阶修改的原始多轮对话文本列表（可选）

    返回：
        包含 literacy_report、literacy_data、modification_stats 的结果字典
    """
    graph = build_phase3_graph()
    initial_state = {
        "v1_essay": v1_essay,
        "v6_essay": v6_essay,
        "topic": topic,
        "revision_events": revision_events,
        "sentence_decisions": sentence_decisions,
        "high_order_history": high_order_history or [],
        "modification_stats": None,
        "literacy_report": None,
        "literacy_data": None,
        "phase3_complete": False,
    }

    print("正在分析写作反馈素养，请稍候...\n")
    result = graph.invoke(initial_state)
    return result


# ============================================================
# CLI 入口
# ============================================================
def main():
    print("=" * 60)
    print("          阶段三：写作反馈素养评估")
    print("=" * 60)
    print()

    # 从阶段二结果文件读取数据
    phase2_file = "phase2_result.json"
    if not os.path.exists(phase2_file):
        print(f"未找到 {phase2_file}，请先运行 run_phase2.py 生成阶段二结果。")
        return

    with open(phase2_file, encoding="utf-8") as f:
        phase2_data = json.load(f)

    v1_essay = phase2_data.get("v1_essay", "")
    v6_essay = phase2_data.get("v6_essay", "")
    topic = phase2_data.get("topic", "")
    revision_events = phase2_data.get("revision_events", [])
    sentence_decisions = phase2_data.get("sentence_decisions", [])

    if not v1_essay or not v6_essay:
        print("phase2_result.json 中缺少 v1_essay 或 v6_essay 字段，无法运行阶段三。")
        return

    result = run_phase3(
        v1_essay=v1_essay,
        v6_essay=v6_essay,
        topic=topic,
        revision_events=revision_events,
        sentence_decisions=sentence_decisions,
    )

    # ── 终端输出 ──────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("          写作反馈素养评估报告")
    print("=" * 60)
    print(result.get("literacy_report", ""))

    stats = result.get("modification_stats") or {}
    if stats:
        print("\n" + "-" * 60)
        print("【修改行为统计】")
        print(f"  总修改事件：{stats.get('total_events', 0)}")
        print(f"  高阶修改：{stats.get('total_high_order', 0)}")
        print(f"  低阶修改：{stats.get('total_low_order', 0)}")
        print(f"  高阶批注率：{stats.get('high_order_annotation_rate', 0)*100:.0f}%")
        print(f"  低阶批注率：{stats.get('low_order_annotation_rate', 0)*100:.0f}%")
        print("\n  修改策略分布：")
        for k, v in (stats.get("modification_strategy") or {}).items():
            print(f"    {k}: {v} 次")
        print("\n  反馈吸收分布：")
        for k, v in (stats.get("feedback_absorption") or {}).items():
            print(f"    {k}: {v} 次")

    # ── 保存结果 ──────────────────────────────────────────────
    output = {
        "literacy_report": result.get("literacy_report"),
        "literacy_data": result.get("literacy_data"),
        "modification_stats": stats,
    }
    with open("phase3_result.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    with open("literacy_report.txt", "w", encoding="utf-8") as f:
        f.write(result.get("literacy_report", ""))

    print("\n结果已保存至 phase3_result.json 和 literacy_report.txt")


if __name__ == "__main__":
    main()
