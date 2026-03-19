import json
import re
import uuid
from datetime import datetime, timezone

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel
from langgraph.types import interrupt

import config
from phase2.state import Phase2State, SentenceDecision, RevisionEvent
from phase2.prompts import (
    HIGH_ORDER_SYSTEM,
    HIGH_ORDER_REGENERATE_SYSTEM,
    PARSE_ACTION_SYSTEM,
    LOW_ORDER_SYSTEM,
    ANNOTATE_EVENT_SYSTEM,
)


def _make_llm(temperature: float = 0.0) -> BaseChatModel:
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_json(text: str) -> dict:
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    return json.loads(text)


def _infer_revision_event(
    phase: str,
    original: str,
    final: str,
    dialogue_history: list,
    decision: str,
    iteration_count: int,
) -> dict:
    """Call LLM to infer RevisionEvent annotation fields."""
    llm = _make_llm(temperature=0.0)
    history_text = "\n".join(f"- {h}" for h in dialogue_history) if dialogue_history else "\uff08\u65e0\uff09"
    phase_label = "\u9ad8\u9636\u4fee\u6539" if phase == "high_order" else "\u4f4e\u9636\u4fee\u6539"
    user_content = (
        f"[\u9636\u6bb5] {phase_label}\n\n"
        f"[\u539f\u59cb\u6587\u672c]\n{original}\n\n"
        f"[\u6700\u7ec8\u91c7\u7528\u6587\u672c]\n{final}\n\n"
        f"[\u5b66\u751f\u5386\u53f2\u8f93\u5165]\n{history_text}\n\n"
        f"[\u5b66\u751f\u51b3\u7b56] {decision}\n"
        f"[\u8fed\u4ee3\u6b21\u6570] {iteration_count}\n\n"
        "\u8bf7\u6839\u636e\u4ee5\u4e0a\u4fe1\u606f\u63a8\u65ad\u5404\u6807\u6ce8\u5b57\u6bb5\u3002"
    )
    response = llm.invoke([
        SystemMessage(content=ANNOTATE_EVENT_SYSTEM),
        HumanMessage(content=user_content),
    ])
    return _parse_json(response.content)


def generate_v2_node(state: Phase2State) -> dict:
    llm = _make_llm(temperature=0.7)
    # Extract CET scores from phase1 backend data for context
    p1 = state.get("phase1_backend_data") or {}
    cet4 = f"{p1.get('cet4_score', '?')}/15 ({p1.get('cet4_band', '')})"
    cet6 = f"{p1.get('cet6_score', '?')}/15 ({p1.get('cet6_band', '')})"
    word_count = len(state['essay'].split())
    user_content = (
        f"[Topic]\n{state['topic']}\n\n"
        f"[Original Essay V1 — {word_count} words]\n{state['essay']}\n\n"
        f"[Phase 1 Scores] CET-4: {cet4} | CET-6: {cet6}\n\n"
        f"[Argumentation Weaknesses]\n{state['argumentation_weaknesses']}\n\n"
        f"[Discourse Weaknesses]\n{state['discourse_weaknesses']}\n\n"
        "IMPORTANT: The revised essay must be 150-200 words (CET-4 standard) or 180-220 words (CET-6 standard). "
        "Do NOT exceed 250 words regardless of the original length.\n\n"
        "Please revise the essay based on the above weaknesses."
    )
    response = llm.invoke([
        SystemMessage(content=HIGH_ORDER_SYSTEM),
        HumanMessage(content=user_content),
    ])
    parsed = _parse_json(response.content)
    v2 = parsed["revised_essay"]
    summary = parsed.get("change_summary", [])
    bullets = "\n".join(f"- {s}" for s in summary)
    display = f"[V2 Draft]\n\n{v2}\n\n[Key Changes]\n{bullets}"
    return {"v2_draft": v2, "high_order_history": [display], "high_order_change_summary": summary}


def present_v2_node(state: Phase2State) -> dict:
    iteration = state["high_order_iteration"]
    latest = state["high_order_history"][-1]
    if iteration == 0:
        prompt = (
            f"{latest}\n\n"
            "Options:\n"
            "1. Accept this revision (type: accept / ok / yes)\n"
            "2. Request further changes (describe your requirements)\n"
            "3. Edit yourself (type: self edit)"
        )
    else:
        prompt = (
            f"[Revision #{iteration}]\n\n{latest}\n\n"
            "Options:\n"
            "1. Accept  2. Request more changes  3. Edit yourself"
        )
    student_input = interrupt(value=prompt)
    # Parse special UI commands: "self_edit_then_ai|||<essay>" or "self_edit_final|||<essay>"
    if "|||" in student_input:
        cmd, text = student_input.split("|||", 1)
        if cmd == "self_edit_final":
            return {"high_order_student_input": student_input, "high_order_action": "self_edit_final", "v4_essay": text}
        elif cmd == "self_edit_then_ai":
            return {"high_order_student_input": text, "high_order_action": "self_edit"}
    return {"high_order_student_input": student_input}


def parse_high_order_action_node(state: Phase2State) -> dict:
    llm = _make_llm(temperature=0.0)
    response = llm.invoke([
        SystemMessage(content=PARSE_ACTION_SYSTEM),
        HumanMessage(content=state["high_order_student_input"]),
    ])
    action = response.content.strip().lower()
    if action not in ("accept_all", "request_changes", "self_edit"):
        action = "request_changes"
    return {"high_order_action": action}


def accept_high_order_node(state: Phase2State) -> dict:
    v4 = state["v2_draft"]
    # Include both AI drafts and student inputs for accurate inference
    history = state["high_order_history"][:]
    if state.get("high_order_student_input"):
        history.append(f"[学生输入] {state['high_order_student_input']}")
    inferred = _infer_revision_event(
        phase="high_order",
        original=state["essay"],
        final=v4,
        dialogue_history=history,
        decision="\u63a5\u53d7AI\u4fee\u6539\u7248\u672c",
        iteration_count=state["high_order_iteration"],
    )
    event: RevisionEvent = {
        "event_id": str(uuid.uuid4()),
        "phase": "high_order",
        "target": v4,
        "modification_strategy": inferred["modification_strategy"],
        "modification_focus": inferred["modification_focus"],
        "modification_type": inferred["modification_type"],
        "modification_depth": "\u9ad8\u9636\u4fee\u6539",
        "feedback_absorption": inferred["feedback_absorption"],
        "dialogue_act": inferred["dialogue_act"],
        "timestamp": _now(),
    }
    return {"v4_essay": v4, "revision_events": [event]}


def regenerate_high_order_node(state: Phase2State) -> dict:
    llm = _make_llm(temperature=0.7)
    history_text = "\n\n---\n\n".join(state["high_order_history"])
    user_content = (
        f"[Topic]\n{state['topic']}\n\n"
        f"[Original Essay V1]\n{state['essay']}\n\n"
        f"[Previous Drafts]\n{history_text}\n\n"
        f"[Student Request]\n{state['high_order_student_input']}\n\n"
        "Please generate a new revision based on the student request."
    )
    response = llm.invoke([
        SystemMessage(content=HIGH_ORDER_REGENERATE_SYSTEM),
        HumanMessage(content=user_content),
    ])
    parsed = _parse_json(response.content)
    new_draft = parsed["revised_essay"]
    summary = parsed.get("change_summary", [])
    bullets = "\n".join(f"- {s}" for s in summary)
    display = f"[Revised Draft]\n\n{new_draft}\n\n[Changes This Round]\n{bullets}"
    return {
        "v2_draft": new_draft,
        "high_order_history": [display],
        "high_order_change_summary": summary,
        "high_order_iteration": state["high_order_iteration"] + 1,
    }


def self_edit_high_order_node(state: Phase2State) -> dict:
    student_essay = interrupt(value="Please enter your own revised essay:")
    history = state["high_order_history"][:]
    if state.get("high_order_student_input"):
        history.append(f"[学生输入] {state['high_order_student_input']}")
    inferred = _infer_revision_event(
        phase="high_order",
        original=state["essay"],
        final=student_essay,
        dialogue_history=history,
        decision="\u5b66\u751f\u81ea\u884c\u4fee\u6539\u540e\u63d0\u4ea4",
        iteration_count=state["high_order_iteration"],
    )
    event: RevisionEvent = {
        "event_id": str(uuid.uuid4()),
        "phase": "high_order",
        "target": student_essay,
        "modification_strategy": inferred["modification_strategy"],
        "modification_focus": inferred["modification_focus"],
        "modification_type": inferred["modification_type"],
        "modification_depth": "\u9ad8\u9636\u4fee\u6539",
        "feedback_absorption": inferred["feedback_absorption"],
        "dialogue_act": inferred["dialogue_act"],
        "timestamp": _now(),
    }
    return {"v4_essay": student_essay, "revision_events": [event]}


def split_sentences_node(state: Phase2State) -> dict:
    essay = state["v4_essay"]
    sentences = re.split(r'(?<=[.!?])\s+', essay.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    return {
        "v4_sentences": sentences,
        "current_sentence_index": 0,
        "low_order_iteration_count": 0,
    }


def generate_sentence_suggestion_node(state: Phase2State) -> dict:
    idx = state["current_sentence_index"]
    sentence = state["v4_sentences"][idx]
    llm = _make_llm(temperature=0.5)
    response = llm.invoke([
        SystemMessage(content=LOW_ORDER_SYSTEM),
        HumanMessage(content=f"[Original Sentence]\n{sentence}"),
    ])
    parsed = _parse_json(response.content)
    suggestion = parsed.get("suggestion", sentence)
    revision_type = parsed.get("revision_type", "none")
    # Reset history for new sentence
    history = [{"suggestion": suggestion, "revision_type": revision_type, "student_request": None}]
    return {
        "current_ai_suggestion": suggestion,
        "current_revision_type": revision_type,
        "current_sentence_history": history,
        "low_order_iteration_count": state["low_order_iteration_count"] + 1,
        "current_low_order_action": "accept" if revision_type == "none" else None,
    }


def present_sentence_node(state: Phase2State) -> dict:
    idx = state["current_sentence_index"]
    total = len(state["v4_sentences"])
    original = state["v4_sentences"][idx]
    suggestion = state["current_ai_suggestion"]
    revision_type = state.get("current_revision_type", "")
    type_map = {
        "grammar": "Grammar", "vocabulary": "Vocabulary",
        "syntax": "Syntax", "cohesion": "Cohesion", "none": "No change needed",
    }
    type_label = type_map.get(revision_type, revision_type)
    prompt = (
        f"[Sentence {idx + 1}/{total}]\n\n"
        f"Original : {original}\n"
        f"Suggested: {suggestion}\n"
        f"Type     : {type_label}\n\n"
        "Options:\n"
        "1. Accept suggestion (type: accept)\n"
        "2. Keep original    (type: keep)\n"
        "3. Request alternative (describe or type: alternative)"
    )
    student_input = interrupt(value=prompt)
    # Parse special UI commands: "self_sentence_final|||<sentence>" or "self_sentence_ai|||<sentence>"
    if "|||" in student_input:
        cmd, text = student_input.split("|||", 1)
        if cmd == "self_sentence_final":
            return {"high_order_student_input": student_input, "current_low_order_action": "self_sentence_final", "current_ai_suggestion": text}
        elif cmd == "self_sentence_ai":
            # Treat student's sentence as new "original" for AI to refine — store as suggestion seed
            return {"high_order_student_input": text, "current_low_order_action": "request_alternative"}
    return {"high_order_student_input": student_input}


def _parse_low_order_action(text: str) -> str:
    text = text.strip().lower()
    if re.search(r"accept|\byes\b|\bok\b|good|fine", text):
        return "accept"
    if re.search(r"keep|original|retain", text):
        return "keep_original"
    return "request_alternative"


def accept_sentence_node(state: Phase2State) -> dict:
    idx = state["current_sentence_index"]
    original = state["v4_sentences"][idx]
    suggestion = state["current_ai_suggestion"]
    revision_type = state.get("current_revision_type", "grammar")
    is_no_change = revision_type == "none"
    history = state.get("current_sentence_history") or []
    dialogue_history = []
    for h in history:
        if h.get("suggestion"):
            dialogue_history.append(f"[AI建议] {h['suggestion']}")
        if h.get("student_request"):
            dialogue_history.append(f"[学生输入] {h['student_request']}")
    if state.get("high_order_student_input"):
        dialogue_history.append(f"[学生输入] {state['high_order_student_input']}")
    decision = "\u786e\u8ba4\u65e0\u9700\u4fee\u6539" if is_no_change else "\u63a5\u53d7AI\u5efa\u8bae"
    inferred = _infer_revision_event(
        phase="low_order",
        original=original,
        final=suggestion,
        dialogue_history=dialogue_history,
        decision=decision,
        iteration_count=state["low_order_iteration_count"],
    )
    event: RevisionEvent = {
        "event_id": str(uuid.uuid4()),
        "phase": "low_order",
        "target": suggestion,
        "modification_strategy": inferred["modification_strategy"],
        "modification_focus": inferred["modification_focus"],
        "modification_type": inferred["modification_type"],
        "modification_depth": "\u4f4e\u9636\u4fee\u6539",
        "feedback_absorption": inferred["feedback_absorption"],
        "dialogue_act": inferred["dialogue_act"],
        "timestamp": _now(),
    }
    decision_: SentenceDecision = {
        "index": idx,
        "original": original,
        "ai_suggestion": suggestion,
        "final": suggestion,
        "decision": "no_change_needed" if is_no_change else "accept",
        "revision_type": revision_type,
        "iteration_count": state["low_order_iteration_count"],
        "revision_event": event,
    }
    return {
        "sentence_decisions": [decision_],
        "revision_events": [event],
        "current_sentence_index": idx + 1,
        "low_order_iteration_count": 0,
        "current_sentence_history": None,
    }


def keep_sentence_node(state: Phase2State) -> dict:
    idx = state["current_sentence_index"]
    original = state["v4_sentences"][idx]
    history = state.get("current_sentence_history") or []
    dialogue_history = []
    for h in history:
        if h.get("suggestion"):
            dialogue_history.append(f"[AI建议] {h['suggestion']}")
        if h.get("student_request"):
            dialogue_history.append(f"[学生输入] {h['student_request']}")
    if state.get("high_order_student_input"):
        dialogue_history.append(f"[学生输入] {state['high_order_student_input']}")
    inferred = _infer_revision_event(
        phase="low_order",
        original=original,
        final=original,
        dialogue_history=dialogue_history,
        decision="\u4fdd\u7559\u539f\u53e5\uff0c\u62d2\u7edcAI\u5efa\u8bae",
        iteration_count=state["low_order_iteration_count"],
    )
    event: RevisionEvent = {
        "event_id": str(uuid.uuid4()),
        "phase": "low_order",
        "target": original,
        "modification_strategy": inferred["modification_strategy"],
        "modification_focus": inferred["modification_focus"],
        "modification_type": inferred["modification_type"],
        "modification_depth": "\u4f4e\u9636\u4fee\u6539",
        "feedback_absorption": inferred["feedback_absorption"],
        "dialogue_act": inferred["dialogue_act"],
        "timestamp": _now(),
    }
    decision: SentenceDecision = {
        "index": idx,
        "original": original,
        "ai_suggestion": state["current_ai_suggestion"],
        "final": original,
        "decision": "keep_original",
        "revision_type": state.get("current_revision_type", "none"),
        "iteration_count": state["low_order_iteration_count"],
        "revision_event": event,
    }
    return {
        "sentence_decisions": [decision],
        "revision_events": [event],
        "current_sentence_index": idx + 1,
        "low_order_iteration_count": 0,
        "current_sentence_history": None,
    }


def regenerate_sentence_node(state: Phase2State) -> dict:
    idx = state["current_sentence_index"]
    original = state["v4_sentences"][idx]
    student_request = state["high_order_student_input"]
    llm = _make_llm(temperature=0.7)
    # Build history context
    history = state.get("current_sentence_history") or []
    history_text = ""
    for i, h in enumerate(history):
        req = f" (student request: {h['student_request']})" if h.get("student_request") else ""
        history_text += f"  Version {i+1}{req}: {h['suggestion']}\n"
    user_content = (
        f"[Original Sentence]\n{original}\n\n"
        f"[Previous Suggestions]\n{history_text}\n"
        f"[Student Request for This Round]\n{student_request}\n\n"
        "Please provide a new suggestion that improves on all previous versions."
    )
    response = llm.invoke([
        SystemMessage(content=LOW_ORDER_SYSTEM),
        HumanMessage(content=user_content),
    ])
    parsed = _parse_json(response.content)
    new_suggestion = parsed.get("suggestion", original)
    new_type = parsed.get("revision_type", "grammar")
    # Append to history
    new_history = history + [{"suggestion": new_suggestion, "revision_type": new_type, "student_request": student_request}]
    return {
        "current_ai_suggestion": new_suggestion,
        "current_revision_type": new_type,
        "current_sentence_history": new_history,
        "low_order_iteration_count": state["low_order_iteration_count"] + 1,
    }


def assemble_v6_node(state: Phase2State) -> dict:
    decisions = sorted(state["sentence_decisions"], key=lambda d: d["index"])
    v6 = " ".join(d["final"] for d in decisions)
    return {"v6_essay": v6, "phase2_complete": True}


def route_high_order(state: Phase2State) -> str:
    action = state["high_order_action"]
    # self_edit_final: v4_essay already set in present_v2_node, route to split_sentences directly
    if action == "self_edit_final":
        return "accept_all"  # v4 already set, skip self_edit node
    return action


def route_low_order(state: Phase2State) -> str:
    # Check if a direct action was set by present_sentence_node
    direct = state.get("current_low_order_action")
    if direct == "self_sentence_final":
        return "accept"   # current_ai_suggestion holds the student sentence, accept it
    return _parse_low_order_action(state["high_order_student_input"] or "")


def route_sentence_loop(state: Phase2State) -> str:
    idx = state["current_sentence_index"]
    total = len(state["v4_sentences"])
    return "continue" if idx < total else "done"
