from typing import TypedDict, Optional


class Phase3State(TypedDict):
    # Input from Phase 2
    v1_essay: str
    v6_essay: str
    topic: str
    revision_events: list        # list[RevisionEvent] — 结构化修改事件
    sentence_decisions: list     # list[SentenceDecision] — 逐句决策
    high_order_history: Optional[list]  # 高阶修改的原始多轮对话文本列表

    # Computed
    modification_stats: Optional[dict]

    # Output
    literacy_report: Optional[str]   # 呈现给学生的文字报告
    literacy_data: Optional[dict]    # 结构化数据（留存给研究组）
    phase3_complete: bool
