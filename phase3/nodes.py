import json
import re

from langchain_core.messages import SystemMessage, HumanMessage

import config
from phase3.state import Phase3State
from phase3.prompts import LITERACY_REPORT_SYSTEM


def _make_llm(temperature: float = 0.0):
    if config.API_PROVIDER == "siliconflow":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.SILICONFLOW_MODEL,
            api_key=config.SILICONFLOW_API_KEY,
            base_url=config.SILICONFLOW_BASE_URL,
            temperature=temperature,
        )
    else:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=config.ANTHROPIC_MODEL,
            api_key=config.ANTHROPIC_API_KEY,
            temperature=temperature,
        )


def _parse_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    return json.loads(text)


def compute_stats_node(state: Phase3State) -> dict:
    """统计学生各类修改行为、批注的频次。"""
    events = state.get("revision_events") or []

    strategy_counts: dict = {}
    focus_counts: dict = {}
    type_counts: dict = {}
    absorption_counts: dict = {}
    dialogue_counts: dict = {}

    total_high = total_low = 0
    high_annotated = low_annotated = 0

    for event in events:
        phase = event.get("phase", "low_order")
        annotation = event.get("student_annotation") or ""

        if phase == "high_order":
            total_high += 1
            if annotation.strip():
                high_annotated += 1
        else:
            total_low += 1
            if annotation.strip():
                low_annotated += 1

        strategy = event.get("modification_strategy", "未知")
        strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

        for focus in event.get("modification_focus") or []:
            focus_counts[focus] = focus_counts.get(focus, 0) + 1

        for mtype in event.get("modification_type") or []:
            type_counts[mtype] = type_counts.get(mtype, 0) + 1

        absorption = event.get("feedback_absorption", "未知")
        absorption_counts[absorption] = absorption_counts.get(absorption, 0) + 1

        dialogue = event.get("dialogue_act", "未知")
        dialogue_counts[dialogue] = dialogue_counts.get(dialogue, 0) + 1

    stats = {
        "total_events": len(events),
        "total_high_order": total_high,
        "total_low_order": total_low,
        "high_order_annotation_count": high_annotated,
        "low_order_annotation_count": low_annotated,
        "high_order_annotation_rate": round(high_annotated / total_high, 2) if total_high > 0 else 0,
        "low_order_annotation_rate": round(low_annotated / total_low, 2) if total_low > 0 else 0,
        "modification_strategy": strategy_counts,
        "modification_focus": focus_counts,
        "modification_type": type_counts,
        "feedback_absorption": absorption_counts,
        "dialogue_act": dialogue_counts,
    }

    return {"modification_stats": stats}


def generate_literacy_report_node(state: Phase3State) -> dict:
    """根据修改行为统计生成写作反馈素养评估报告。"""
    llm = _make_llm(temperature=0.7)
    stats = state.get("modification_stats") or {}
    events = state.get("revision_events") or []

    # 仅取前10条事件避免 token 超限
    sample_events = events[:10]

    # 高阶修改原始对话（去掉过长的 diff 内容只保留学生发言）
    high_history = state.get("high_order_history") or []
    history_block = ""
    if high_history:
        lines = []
        for i, turn in enumerate(high_history):
            # turn 可能是字符串（draft 文本）或 dict
            if isinstance(turn, str):
                lines.append(f"  第{i+1}轮草稿（节选）：{turn[:200]}{'...' if len(turn) > 200 else ''}")
            elif isinstance(turn, dict):
                lines.append(f"  第{i+1}轮：{json.dumps(turn, ensure_ascii=False)[:300]}")
        history_block = "\n".join(lines)

    # 低阶逐句：取有批注或有替代方案的句子作为补充原始证据
    rich_decisions = [
        d for d in (state.get("sentence_decisions") or [])
        if (d.get("revision_event") or {}).get("student_annotation") or d.get("iteration_count", 0) > 0
    ]

    user_content = f"""[作文题目]
{state.get('topic', '')}

[V1 原始作文]
{state.get('v1_essay', '')}

[V6 最终作文]
{state.get('v6_essay', '')}

[修改行为统计（结构化）]
{json.dumps(stats, ensure_ascii=False, indent=2)}

[高阶修改原始对话记录]
{history_block if history_block else '（无高阶修改对话记录）'}

[低阶修改中有学生批注或多次交互的句子（原始证据）]
{json.dumps(rich_decisions[:15], ensure_ascii=False, indent=2)}

[全部修改事件（结构化标注，前{len(sample_events)}条）]
{json.dumps(sample_events, ensure_ascii=False, indent=2)}

请根据以上数据（结构化统计 + 原始交互记录），按照要求生成学生的写作反馈素养评估报告。"""

    response = llm.invoke([
        SystemMessage(content=LITERACY_REPORT_SYSTEM),
        HumanMessage(content=user_content),
    ])

    try:
        parsed = _parse_json(response.content)
    except Exception:
        parsed = {
            "overall_performance": "在本次与智能体的互动中，你积极参与了作文修改过程。",
            "strengths": ["能够理解AI反馈", "愿意与智能体多轮互动", "坚持完成修改流程"],
            "areas_to_improve": ["可以尝试提出更具体的修改要求", "在接受AI建议时可以多思考原因"],
            "suggestion": "下次修改时，尝试在接受或拒绝AI建议前先问自己「为什么」，这能帮助你更快提升写作能力。",
            "literacy_dimensions": {
                "cognitive": "你展示了理解AI反馈的基本能力。",
                "behavioral": "你能够将AI反馈应用到修改中。",
                "emotional": "你保持了良好的参与热情。",
                "ethical": "你在修改中保留了自己的写作风格。",
            }
        }

    # 生成呈现给学生的文字报告
    strengths_text = "\n".join(f"• {s}" for s in parsed.get("strengths", []))
    improve_text = "\n".join(f"• {s}" for s in parsed.get("areas_to_improve", []))
    dims = parsed.get("literacy_dimensions", {})

    report = f"""在与你的多轮互动和作文修改过程中，我也觉察到你使用智能体反馈、理解反馈以及根据反馈进行修改的方式。下面是初步小结：

**1. 整体表现**
{parsed.get('overall_performance', '')}

**2. 你做得比较好的地方（你的优势）**
{strengths_text}

**3. 还有可以继续提升的地方**
{improve_text}

**4. 给你的一个小建议**
{parsed.get('suggestion', '')}

---
**各维度详细评价**

- **认知维度**：{dims.get('cognitive', '')}
- **行为维度**：{dims.get('behavioral', '')}
- **情感维度**：{dims.get('emotional', '')}
- **伦理维度**：{dims.get('ethical', '')}"""

    return {
        "literacy_report": report,
        "literacy_data": parsed,
        "phase3_complete": True,
    }
