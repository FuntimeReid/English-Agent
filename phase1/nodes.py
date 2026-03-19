"""
阶段一节点函数：
  - cet_scoring_node：四六级总体打分
  - six_dim_node：六维度诊断反馈
  - format_report_node：生成最终报告
"""

import json
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

import config
from phase1.state import Phase1State, DimensionResult
from phase1.prompts import (
    CET_SCORING_SYSTEM,
    CET_SCORING_FEW_SHOT,
    SIX_DIM_SYSTEM,
)

# ============================================================
# 维度子描述语数量（用于计算最终得分）
# ============================================================
DIM_DESCRIPTOR_COUNTS = {
    "argumentation": 14,
    "discourse": 8,
    "convention": 4,
    "vocabulary": 8,
    "grammar": 4,
    "syntax": 4,
}

DIM_NAMES_ZH = {
    "argumentation": "论证",
    "discourse": "语篇",
    "convention": "书写规范",
    "vocabulary": "词汇",
    "grammar": "语法",
    "syntax": "句法",
}


def _make_llm(temperature: float = 0.0) -> BaseChatModel:
    """根据 config.API_PROVIDER 返回对应的 LLM 实例。"""
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


def _calc_dim_score(sub_scores: list, dim_name: str) -> float:
    """
    按文档公式计算维度最终得分（0-5分）：
    最终得分 = (所有描述语总分 / 描述语数量) / 4 × 5
    """
    count = DIM_DESCRIPTOR_COUNTS[dim_name]
    if len(sub_scores) != count:
        # 数量不对时按实际数量计算
        count = len(sub_scores)
    if count == 0:
        return 0.0
    return round((sum(sub_scores) / count) / 4 * 5, 1)


# ============================================================
# Node 1：CET 四六级总体打分
# ============================================================
def cet_scoring_node(state: Phase1State) -> dict:
    """对学生作文分别按四级和六级标准进行总体印象打分。"""
    llm = _make_llm(temperature=0.0)

    user_content = f"""{CET_SCORING_FEW_SHOT}

---现在请对以下学生作文进行评分---

题目：
{state['topic']}

学生作文：
{state['essay']}

请严格按照要求的 JSON 格式输出四级和六级评分结果。只输出 JSON，不要有任何其他内容。
"""

    messages = [
        SystemMessage(content=CET_SCORING_SYSTEM),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    # 解析 JSON（容错处理：去掉可能的 markdown 代码块）
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    return {
        "cet4_score": result["cet4_score"],
        "cet4_band": result["cet4_band"],
        "cet4_rationale": result["cet4_rationale"],
        "cet6_score": result["cet6_score"],
        "cet6_band": result["cet6_band"],
        "cet6_rationale": result["cet6_rationale"],
    }


# ============================================================
# Node 2：六维度诊断反馈
# ============================================================
def six_dim_node(state: Phase1State) -> dict:
    """对学生作文进行六维度详细诊断，计算各维度最终得分。"""
    llm = _make_llm(temperature=0.0)

    user_content = f"""【总体参考（仅供整体了解，不限制各维度得分范围）】
四级总分：{state['cet4_score']} / 15（{state['cet4_band']}）
六级总分：{state['cet6_score']} / 15（{state['cet6_band']}）
注意：各维度独立评分，某维度可以远高于或远低于总体水平，请如实反映。

题目：
{state['topic']}

学生作文：
{state['essay']}

请严格按照要求的 JSON 格式输出六个维度的评分结果。只输出 JSON，不要有任何其他内容。
"""

    messages = [
        SystemMessage(content=SIX_DIM_SYSTEM),
        HumanMessage(content=user_content),
    ]

    response = llm.invoke(messages)
    raw = response.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    result = json.loads(raw)

    updates = {}
    for dim in ["argumentation", "discourse", "convention", "vocabulary", "grammar", "syntax"]:
        dim_data = result[dim]
        sub_scores = dim_data["sub_scores"]
        final_score = _calc_dim_score(sub_scores, dim)
        updates[dim] = DimensionResult(
            sub_scores=sub_scores,
            final_score=final_score,
            strengths=dim_data["strengths"],
            weaknesses=dim_data["weaknesses"],
        )

    return updates


# ============================================================
# Node 3：格式化最终报告
# ============================================================
def format_report_node(state: Phase1State) -> dict:
    """将所有评分汇总，生成呈现给学生的报告和研究组后台数据。"""
    from phase1.descriptors import ALL_DESCRIPTORS

    # ---------- 学生报告 ----------
    lines = []
    lines.append("=" * 60)
    lines.append("英语写作评分与诊断报告".center(60))
    lines.append("=" * 60)

    lines.append("\n【总体评分】")
    lines.append(f"  四级标准得分：{state['cet4_score']} / 15  ({state['cet4_band']})")
    lines.append(f"  六级标准得分：{state['cet6_score']} / 15  ({state['cet6_band']})")
    lines.append(f"\n  四级评分说明：{state['cet4_rationale']}")
    lines.append(f"  六级评分说明：{state['cet6_rationale']}")

    lines.append("\n【六维度诊断反馈】")
    dim_order = [
        ("argumentation", "论证能力"),
        ("discourse",     "语篇能力"),
        ("convention",    "书写规范"),
        ("vocabulary",    "词汇"),
        ("grammar",       "语法"),
        ("syntax",        "句法"),
    ]

    for dim_key, dim_name_zh in dim_order:
        dim: DimensionResult = state.get(dim_key)
        if not dim:
            continue
        lines.append(f"\n  ▸ {dim_name_zh}  {dim['final_score']:.1f} / 5.0")
        lines.append(f"    强项：{dim['strengths']}")
        lines.append(f"    弱项：{dim['weaknesses']}")

    lines.append("\n" + "=" * 60)
    student_report = "\n".join(lines)

    # ---------- 后台数据（研究组）----------
    def build_detail_table(dim_key: str, sub_scores: list) -> list:
        """将子描述语得分与描述语定义合并，生成逐条记录表。"""
        descriptors = ALL_DESCRIPTORS[dim_key]
        table = []
        for i, descriptor in enumerate(descriptors):
            row = dict(descriptor)          # 复制描述语字段（维度/子维度/描述语）
            row["得分"] = sub_scores[i] if i < len(sub_scores) else None
            table.append(row)
        return table

    backend_data = {
        "cet4_score":    state["cet4_score"],
        "cet4_band":     state["cet4_band"],
        "cet4_rationale": state["cet4_rationale"],
        "cet6_score":    state["cet6_score"],
        "cet6_band":     state["cet6_band"],
        "cet6_rationale": state["cet6_rationale"],
        "dimensions": {},
    }

    for dim_key, dim_name_zh in dim_order:
        dim: DimensionResult = state.get(dim_key)
        if not dim:
            continue
        backend_data["dimensions"][dim_key] = {
            "name_zh":    dim_name_zh,
            "final_score": dim["final_score"],
            "strengths":  dim["strengths"],
            "weaknesses": dim["weaknesses"],
            "detail_table": build_detail_table(dim_key, dim["sub_scores"]),
        }

    return {
        "student_report": student_report,
        "backend_data":   backend_data,
    }
