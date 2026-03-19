from typing import TypedDict, Optional, Literal, Annotated
import operator


class RevisionEvent(TypedDict):
    event_id: str
    phase: Literal["high_order", "low_order"]
    target: str
    modification_strategy: Literal[
        "AI修改",
        "基于AI反馈的学生修改",
        "自己修改",
        "拒绝AI反馈的学生修改",
        "忽略/拒绝修改",
    ]
    modification_focus: list[Literal["内容修改", "语言修改", "结构修改"]]
    modification_type: list[Literal[
        "重写",
        "添加",
        "替换",
        "删除",
        "重新调整",
    ]]
    modification_depth: Literal["高阶修改", "低阶修改"]
    feedback_absorption: Literal[
        "完全吸收不做反思",
        "完全吸收有反思",
        "部分吸收",
        "忽略",
        "分歧困惑",
        "无需修改",
    ]
    dialogue_act: Literal[
        "初步请求",
        "宏观提问",
        "表层提问",
        "深层提问",
        "进一步修改",
        "成果检验",
        "元反思与回顾",
    ]
    timestamp: str


class SentenceDecision(TypedDict):
    index: int
    original: str
    ai_suggestion: str
    final: str
    decision: Literal["accept", "keep_original", "alternative_accepted", "self_submitted", "no_change_needed"]
    revision_type: Literal["grammar", "vocabulary", "syntax", "cohesion", "none"]
    iteration_count: int
    revision_event: RevisionEvent


class Phase2State(TypedDict):
    # From Phase 1
    essay: str
    topic: str
    argumentation_weaknesses: str
    discourse_weaknesses: str
    phase1_backend_data: dict

    # High-order revision
    v2_draft: Optional[str]
    high_order_history: Annotated[list[str], operator.add]
    high_order_change_summary: Optional[list]
    high_order_iteration: int
    high_order_student_input: Optional[str]
    high_order_action: Optional[Literal["accept_all", "request_changes", "self_edit", "self_edit_then_ai", "self_edit_final"]]
    v4_essay: Optional[str]

    # Low-order revision
    v4_sentences: Optional[list[str]]
    current_sentence_index: int
    sentence_decisions: Annotated[list[SentenceDecision], operator.add]
    current_ai_suggestion: Optional[str]
    current_revision_type: Optional[str]
    current_sentence_history: Optional[list]  # list of {suggestion, revision_type, student_request}
    current_low_order_action: Optional[Literal["accept", "keep_original", "request_alternative", "self_sentence", "self_sentence_ai", "self_sentence_final"]]
    low_order_iteration_count: int
    v6_essay: Optional[str]

    # Phase 3 log
    revision_events: Annotated[list[RevisionEvent], operator.add]

    # Control
    phase2_complete: bool
