import streamlit as st
from run_phase1 import run_phase1
from phase2.graph import build_phase2_graph
import json
from datetime import datetime
from phase1.excel_exporter import export_to_excel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

st.set_page_config(
    page_title="\u4f5c\u6587\u8bc4\u5206\u7cfb\u7edf",
    page_icon="\U0001f9e0",
    layout="wide"
)

st.markdown("""
<style>
.main { padding: 2rem; }
.stButton>button {
    border-radius: 10px;
    height: 3em;
    font-size: 15px;
}
.block-container { padding-top: 2rem; }
.essay-box {
    background-color:#f8f9fa;
    color:#212529;
    padding:20px;
    border-radius:10px;
    border:1px solid #ddd;
    white-space:pre-wrap;
    font-family: monospace;
    line-height: 1.7;
}
.change-box {
    background-color:#fff8e1 !important;
    color:#212529 !important;
    padding:16px;
    border-radius:10px;
    border:1px solid #ffe082;
    white-space:pre-wrap;
}
.prompt-box {
    background-color:#f0f4ff;
    color:#212529;
    padding:20px;
    border-radius:10px;
    border:1px solid #b0c4de;
    white-space:pre-wrap;
}
</style>
""", unsafe_allow_html=True)

# Header
col1, col2 = st.columns([1, 8])
with col1:
    st.image("logo.png", width=150)
with col2:
    st.title("\u4e2d\u82f1\u6587\u667a\u80fd\u4f53 \u00b7 \u4f5c\u6587\u8bc4\u5206\u7cfb\u7edf")
    st.caption("AI Essay Evaluation System")
st.divider()

# Session state init
for key, default in [
    ("phase", "input"),
    ("phase1_result", None),
    ("essay", ""),
    ("topic", ""),
    ("p2_graph", None),
    ("p2_config", None),
    ("p2_state", None),       # latest graph state snapshot
    ("p2_interrupt_type", None),  # "high_order" | "low_order" | "self_edit_high" | "self_edit_low"
    ("p2_sub_action", None),  # which button was clicked: "request_changes" | "self_edit" | "alternative" | "self_sentence"
]:
    if key not in st.session_state:
        st.session_state[key] = default


def _invoke_p2(payload):
    """Invoke phase2 graph and update session state."""
    result = st.session_state.p2_graph.invoke(payload, config=st.session_state.p2_config)
    st.session_state.p2_state = result
    interrupts = result.get("__interrupt__", [])
    if interrupts:
        # Determine interrupt type from current node context
        prompt = interrupts[0].value
        if "Sentence" in prompt:
            st.session_state.p2_interrupt_type = "low_order"
        elif "own revised essay" in prompt:
            st.session_state.p2_interrupt_type = "self_edit_high"
        else:
            st.session_state.p2_interrupt_type = "high_order"
        st.session_state.p2_sub_action = None
        st.session_state.phase = "phase2_running"
    else:
        if result.get("phase2_complete"):
            st.session_state.phase = "phase2_done"
    st.rerun()


# ============================================================
# Phase 1: Input
# ============================================================
if st.session_state.phase == "input":
    left, right = st.columns([1, 1])
    with left:
        st.subheader("\U0001f4cc \u4f5c\u6587\u9898\u76ee")
        topic = st.text_input("\u8bf7\u8f93\u5165\u4f5c\u6587\u9898\u76ee")
    with right:
        st.subheader("\U0001f4dd \u4f5c\u6587\u5185\u5bb9")
        essay = st.text_area("\u8bf7\u8f93\u5165\u4f5c\u6587", height=250)

    if st.button("\U0001f680 \u5f00\u59cb\u8bc4\u5206", use_container_width=True):
        if not topic or not essay:
            st.warning("\u8bf7\u586b\u5199\u5b8c\u6574\u4fe1\u606f")
        else:
            with st.spinner("AI \u6b63\u5728\u5206\u6790\u4e2d..."):
                result = run_phase1(essay=essay, topic=topic)
            st.session_state.phase1_result = result
            st.session_state.essay = essay
            st.session_state.topic = topic
            st.session_state.phase = "phase1_done"
            st.rerun()


# ============================================================
# Phase 1: Results
# ============================================================
elif st.session_state.phase == "phase1_done":
    result = st.session_state.phase1_result
    st.success("\u2705 \u8bc4\u5206\u5b8c\u6210")
    st.subheader("\U0001f4c4 \u5b66\u751f\u62a5\u544a")
    st.markdown(f'''<div class="essay-box">{result["student_report"]}</div>''', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            label="\U0001f4e5 \u4e0b\u8f7d\u62a5\u544a\uff08TXT\uff09",
            data=result["student_report"],
            file_name="report.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col_b:
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        export_to_excel(result["backend_data"], filepath=filename)
        with open(filename, "rb") as f:
            st.download_button(
                label="\U0001f4ca \u4e0b\u8f7d\u8bc4\u5206\u6570\u636e\uff08Excel\uff09",
                data=f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with st.expander("\U0001f50d \u67e5\u770b\u8be6\u7ec6\u8bc4\u5206\u6570\u636e"):
        st.json(result["backend_data"])

    st.divider()
    if st.button("\u270f\ufe0f \u8fdb\u5165\u9636\u6bb5\u4e8c\uff1a\u667a\u80fd\u4f53\u6279\u9605", use_container_width=True):
        checkpointer = MemorySaver()
        graph = build_phase2_graph(checkpointer=checkpointer)
        p2_config = {"configurable": {"thread_id": "streamlit_session"}}
        st.session_state.p2_graph = graph
        st.session_state.p2_config = p2_config
        st.session_state.p2_sub_action = None

        backend = result["backend_data"]
        dims = backend.get("dimensions", {})
        initial_state = {
            "essay": st.session_state.essay,
            "topic": st.session_state.topic,
            "argumentation_weaknesses": dims.get("argumentation", {}).get("weaknesses", ""),
            "discourse_weaknesses": dims.get("discourse", {}).get("weaknesses", ""),
            "phase1_backend_data": backend,
            "v2_draft": None,
            "high_order_history": [],
            "high_order_change_summary": None,
            "high_order_iteration": 0,
            "high_order_student_input": None,
            "high_order_action": None,
            "v4_essay": None,
            "v4_sentences": None,
            "current_sentence_index": 0,
            "sentence_decisions": [],
            "current_ai_suggestion": None,
            "current_revision_type": None,
            "current_sentence_history": None,
            "current_low_order_action": None,
            "low_order_iteration_count": 0,
            "v6_essay": None,
            "revision_events": [],
            "phase2_complete": False,
        }
        with st.spinner("AI \u6b63\u5728\u751f\u6210\u4fee\u6539\u8349\u7a3f..."):
            _invoke_p2(initial_state)


# ============================================================
# Phase 2: Running
# ============================================================
elif st.session_state.phase == "phase2_running":
    state = st.session_state.p2_state
    interrupts = state.get("__interrupt__", [])
    if not interrupts:
        st.session_state.phase = "phase2_done"
        st.rerun()

    interrupt_type = st.session_state.p2_interrupt_type
    sub_action = st.session_state.p2_sub_action

    # ── High-order interrupt ──────────────────────────────────
    if interrupt_type == "high_order":
        iteration = state.get("high_order_iteration", 0)
        v2 = state.get("v2_draft", "")
        summary = state.get("high_order_change_summary") or []

        st.subheader(f"\u270f\ufe0f \u9ad8\u9636\u4fee\u6539{'\uff08\u7b2c ' + str(iteration) + ' \u6b21\u8c03\u6574\uff09' if iteration > 0 else ''}")

        left_col, right_col = st.columns([3, 2])
        with left_col:
            st.markdown("**\U0001f4c4 \u4fee\u6539\u540e\u7684\u6587\u7ae0**")
            st.markdown(f'''<div class="essay-box">{v2}</div>''', unsafe_allow_html=True)
        with right_col:
            st.markdown("**\U0001f4dd \u4e3b\u8981\u4fee\u6539\u70b9**")
            if summary:
                changes_text = "\n".join(f"\u2022 {s}" for s in summary)
            else:
                changes_text = "\u6682\u65e0\u4fee\u6539\u8bf4\u660e"
            st.markdown(f'''<div class="change-box">{changes_text}</div>''', unsafe_allow_html=True)

        st.divider()

        if sub_action is None:
            st.markdown("**\u8bf7\u9009\u62e9\u64cd\u4f5c\uff1a**")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("\u2705 \u63a5\u53d7\u6b64\u7248\u672c", use_container_width=True):
                    with st.spinner("AI \u5904\u7406\u4e2d..."):
                        _invoke_p2(Command(resume="accept"))
            with c2:
                if st.button("\U0001f4ac \u5411AI\u63d0\u51fa\u4fee\u6539\u610f\u89c1", use_container_width=True):
                    st.session_state.p2_sub_action = "request_changes"
                    st.rerun()
            with c3:
                if st.button("\u270d\ufe0f \u63d0\u4ea4\u81ea\u5df1\u7684\u7248\u672c", use_container_width=True):
                    st.session_state.p2_sub_action = "self_edit"
                    st.rerun()

        elif sub_action == "request_changes":
            st.markdown("**\u8bf7\u63cf\u8ff0\u4f60\u7684\u4fee\u6539\u8981\u6c42\uff1a**")
            user_req = st.text_area("\u4fee\u6539\u610f\u89c1", height=100, key="high_req_input")
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("\u8fd4\u56de", use_container_width=True):
                    st.session_state.p2_sub_action = None
                    st.rerun()
            with c2:
                if st.button("\U0001f4e4 \u53d1\u9001\u7ed9AI", use_container_width=True):
                    if user_req.strip():
                        with st.spinner("AI \u6b63\u5728\u91cd\u65b0\u751f\u6210..."):
                            _invoke_p2(Command(resume=user_req.strip()))
                    else:
                        st.warning("\u8bf7\u8f93\u5165\u4fee\u6539\u610f\u89c1")

        elif sub_action == "self_edit":
            st.markdown("**\u8bf7\u8f93\u5165\u4f60\u81ea\u5df1\u4fee\u6539\u540e\u7684\u5b8c\u6574\u6587\u7ae0\uff1a**")
            self_text = st.text_area("\u81ea\u5df1\u7684\u7248\u672c", height=300, key="high_self_input", value=v2)
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("\u8fd4\u56de", use_container_width=True):
                    st.session_state.p2_sub_action = None
                    st.rerun()
            with c2:
                if st.button("\U0001f916 \u8ba9AI\u57fa\u4e8e\u6b64\u7248\u672c\u7ee7\u7eed\u4f18\u5316", use_container_width=True):
                    if self_text.strip():
                        with st.spinner("AI \u5904\u7406\u4e2d..."):
                            _invoke_p2(Command(resume=f"self_edit_then_ai|||{self_text.strip()}"))
                    else:
                        st.warning("\u8bf7\u8f93\u5165\u6587\u7ae0")
            with c3:
                if st.button("\u2705 \u76f4\u63a5\u4f5c\u4e3a\u5b9a\u7a3f\u63d0\u4ea4", use_container_width=True):
                    if self_text.strip():
                        with st.spinner("\u5904\u7406\u4e2d..."):
                            _invoke_p2(Command(resume=f"self_edit_final|||{self_text.strip()}"))
                    else:
                        st.warning("\u8bf7\u8f93\u5165\u6587\u7ae0")

    # ── Self-edit high-order (second interrupt for self_edit path) ──
    elif interrupt_type == "self_edit_high":
        st.subheader("\u270d\ufe0f \u8f93\u5165\u81ea\u5df1\u4fee\u6539\u7684\u6587\u7ae0")
        self_text = st.text_area("\u81ea\u5df1\u7684\u7248\u672c", height=300, key="self_edit_high_input")
        if st.button("\u2705 \u63d0\u4ea4", use_container_width=True):
            if self_text.strip():
                with st.spinner("\u5904\u7406\u4e2d..."):
                    _invoke_p2(Command(resume=self_text.strip()))
            else:
                st.warning("\u8bf7\u8f93\u5165\u6587\u7ae0")

    # ── Low-order interrupt ───────────────────────────────────
    elif interrupt_type == "low_order":
        idx = state.get("current_sentence_index", 0)
        sentences = state.get("v4_sentences") or []
        total = len(sentences)
        original = sentences[idx - 1] if idx > 0 and sentences else ""
        # current_sentence_index was already incremented? No — it increments after decision.
        # At interrupt time, index hasn't been incremented yet.
        cur_idx = idx
        original = sentences[cur_idx] if cur_idx < len(sentences) else ""
        suggestion = state.get("current_ai_suggestion", "")
        revision_type = state.get("current_revision_type", "none")
        type_map = {
            "grammar": "\u8bed\u6cd5", "vocabulary": "\u8bcd\u6c47",
            "syntax": "\u53e5\u5f0f", "cohesion": "\u8854\u63a5", "none": "\u65e0\u9700\u4fee\u6539",
        }
        type_zh = type_map.get(revision_type, revision_type)

        st.subheader(f"\u2702\ufe0f \u4f4e\u9636\u4fee\u6539 \u2014 \u7b2c {cur_idx + 1} / {total} \u53e5")

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**\u539f\u53e5**")
            st.markdown(f'''<div class="prompt-box">{original}</div>''', unsafe_allow_html=True)
        with col_r:
            st.markdown(f"**AI \u5efa\u8bae** <span style='background:#e8f5e9;padding:2px 8px;border-radius:4px;font-size:13px;'>{type_zh}</span>", unsafe_allow_html=True)
            if revision_type == "none":
                st.markdown('''<div class="change-box">\u6b64\u53e5\u65e0\u9700\u4fee\u6539</div>''', unsafe_allow_html=True)
            else:
                st.markdown(f'''<div class="change-box">{suggestion}</div>''', unsafe_allow_html=True)

        st.divider()

        if sub_action is None:
            c1, c2, c3 = st.columns(3)
            with c1:
                btn_label = "\u2705 \u786e\u8ba4\uff08\u65e0\u9700\u4fee\u6539\uff09" if revision_type == "none" else "\u2705 \u63a5\u53d7\u5efa\u8bae"
                if st.button(btn_label, use_container_width=True):
                    with st.spinner("\u5904\u7406\u4e2d..."):
                        _invoke_p2(Command(resume="accept"))
            with c2:
                if st.button("\U0001f504 \u8981\u6c42\u6362\u4e00\u79cd\u6539\u6cd5", use_container_width=True):
                    st.session_state.p2_sub_action = "alternative"
                    st.rerun()
            with c3:
                if st.button("\u270d\ufe0f \u81ea\u5df1\u4fee\u6539\u6b64\u53e5", use_container_width=True):
                    st.session_state.p2_sub_action = "self_sentence"
                    st.rerun()

        elif sub_action == "alternative":
            st.markdown("**\u63cf\u8ff0\u4f60\u5e0c\u671b\u7684\u6539\u6cd5\uff08\u53ef\u7559\u7a7a\u8ba9AI\u81ea\u884c\u91cd\u65b0\u751f\u6210\uff09\uff1a**")
            alt_req = st.text_input("\u4fee\u6539\u8981\u6c42", key="alt_req_input")
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("\u8fd4\u56de", use_container_width=True):
                    st.session_state.p2_sub_action = None
                    st.rerun()
            with c2:
                if st.button("\U0001f4e4 \u53d1\u9001", use_container_width=True):
                    payload = alt_req.strip() if alt_req.strip() else "alternative"
                    with st.spinner("AI \u91cd\u65b0\u751f\u6210\u4e2d..."):
                        _invoke_p2(Command(resume=payload))

        elif sub_action == "self_sentence":
            st.markdown("**\u8bf7\u8f93\u5165\u4f60\u81ea\u5df1\u4fee\u6539\u7684\u53e5\u5b50\uff1a**")
            self_sent = st.text_input("\u81ea\u5df1\u7684\u53e5\u5b50", key="self_sent_input", value=original)
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("\u8fd4\u56de", use_container_width=True):
                    st.session_state.p2_sub_action = None
                    st.rerun()
            with c2:
                if st.button("\U0001f916 \u8ba9AI\u57fa\u4e8e\u6b64\u53e5\u7ee7\u7eed\u4f18\u5316", use_container_width=True):
                    if self_sent.strip():
                        with st.spinner("AI \u5904\u7406\u4e2d..."):
                            _invoke_p2(Command(resume=f"self_sentence_ai|||{self_sent.strip()}"))
                    else:
                        st.warning("\u8bf7\u8f93\u5165\u53e5\u5b50")
            with c3:
                if st.button("\u2705 \u76f4\u63a5\u4f5c\u4e3a\u6700\u7ec8\u53e5\u63d0\u4ea4", use_container_width=True):
                    if self_sent.strip():
                        with st.spinner("\u5904\u7406\u4e2d..."):
                            _invoke_p2(Command(resume=f"self_sentence_final|||{self_sent.strip()}"))
                    else:
                        st.warning("\u8bf7\u8f93\u5165\u53e5\u5b50")


# ============================================================
# Phase 2: Done
# ============================================================
elif st.session_state.phase == "phase2_done":
    result = st.session_state.p2_state
    st.success("\u2705 \u6279\u9605\u5b8c\u6210")

    st.subheader("\U0001f4c4 V6 \u6700\u7ec8\u4f5c\u6587")
    st.markdown(f'''<div class="essay-box">{result.get("v6_essay", "")}</div>''', unsafe_allow_html=True)

    st.download_button(
        label="\U0001f4e5 \u4e0b\u8f7d V6 \u4f5c\u6587\uff08TXT\uff09",
        data=result.get("v6_essay", ""),
        file_name="v6_essay.txt",
        mime="text/plain",
        use_container_width=True,
    )

    events = result.get("revision_events", [])
    with st.expander(f"\U0001f4cb \u9636\u6bb5\u4e09\u8bb0\u5f55\uff08\u5171 {len(events)} \u6761\u4fee\u6539\u4e8b\u4ef6\uff09"):
        st.json(events)

    if st.button("\U0001f504 \u91cd\u65b0\u5f00\u59cb", use_container_width=True):
        for key in ["phase", "phase1_result", "essay", "topic",
                    "p2_graph", "p2_config", "p2_state",
                    "p2_interrupt_type", "p2_sub_action"]:
            del st.session_state[key]
        st.rerun()
