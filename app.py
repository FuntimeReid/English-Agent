import json
import re

import streamlit as st
from run_phase1 import run_phase1
from phase2.graph import build_phase2_graph
from phase1.excel_exporter import export_to_excel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from datetime import datetime

st.set_page_config(
    page_title="作文评分系统",
    page_icon="🧠",
    layout="wide"
)

st.markdown("""
<style>
.main { padding: 2rem; }
.stButton>button { border-radius: 10px; height: 3em; font-size: 15px; }
.block-container { padding-top: 2rem; }
.essay-box {
    background-color:#f8f9fa; color:#212529;
    padding:20px; border-radius:10px; border:1px solid #ddd;
    white-space:pre-wrap; font-family: monospace; line-height: 1.7;
}
.change-box {
    background-color:#fff8e1 !important; color:#212529 !important;
    padding:16px; border-radius:10px; border:1px solid #ffe082; white-space:pre-wrap;
}
.prompt-box {
    background-color:#f0f4ff; color:#212529;
    padding:20px; border-radius:10px; border:1px solid #b0c4de; white-space:pre-wrap;
}
.decided-box {
    background-color:#e8f5e9; color:#212529;
    padding:12px; border-radius:8px; border:1px solid #a5d6a7; white-space:pre-wrap;
}
.history-box {
    background-color:#f3e5f5; color:#212529;
    padding:12px; border-radius:8px; border:1px solid #ce93d8; white-space:pre-wrap; font-size:13px;
}
</style>
""", unsafe_allow_html=True)

# Header
col1, col2 = st.columns([1, 8])
with col1:
    st.image("logo.png", width=150)
with col2:
    st.title("中英文智能体 · 作文评分系统")
    st.caption("AI Essay Evaluation System")
st.divider()

# ── Session state 初始化 ──────────────────────────────────────────
for key, default in [
    ("phase", "input"),
    ("phase1_result", None),
    ("essay", ""),
    ("topic", ""),
    ("p2_graph", None),
    ("p2_config", None),
    ("p2_state", None),
    ("p2_interrupt_type", None),
    ("p2_sub_action", None),
    # 低阶批量导航
    ("lo_data", None),
    ("lo_current", 0),
    ("lo_initialized", False),
    # 阶段三
    ("p3_result", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── 辅助：调用阶段二图 ──────────────────────────────────────────
def _invoke_p2(payload):
    result = st.session_state.p2_graph.invoke(payload, config=st.session_state.p2_config)
    st.session_state.p2_state = result
    interrupts = result.get("__interrupt__", [])
    if interrupts:
        prompt = interrupts[0].value
        if prompt == "BATCH_LOW_ORDER":
            st.session_state.p2_interrupt_type = "low_order_nav"
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


# ── 辅助：直接调用 LLM 生成替代方案（不走图）──────────────────────
def _get_alternative(original: str, current_suggestion: str,
                     request: str, alt_history: list) -> str:
    import config
    from langchain_core.messages import SystemMessage, HumanMessage
    from phase2.prompts import LOW_ORDER_SYSTEM

    if config.API_PROVIDER == "siliconflow":
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=config.SILICONFLOW_MODEL,
            api_key=config.SILICONFLOW_API_KEY,
            base_url=config.SILICONFLOW_BASE_URL,
            temperature=0.7,
        )
    else:
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(
            model=config.ANTHROPIC_MODEL,
            api_key=config.ANTHROPIC_API_KEY,
            temperature=0.7,
        )

    prev = ""
    if current_suggestion != original:
        prev += f"  Initial suggestion: {current_suggestion}\n"
    for i, alt in enumerate(alt_history):
        prev += f"  Alternative {i+1}: {alt}\n"

    req = request.strip() if request.strip() else "Please provide a different revision approach."
    user_content = (
        f"[Original Sentence]\n{original}\n\n"
        f"[Previous Suggestions]\n{prev or '(none)'}\n"
        f"[Student Request]\n{req}\n\n"
        "Provide a new alternative suggestion."
    )
    response = llm.invoke([
        SystemMessage(content=LOW_ORDER_SYSTEM),
        HumanMessage(content=user_content),
    ])
    text = response.content.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        text = match.group(1)
    try:
        return json.loads(text).get("suggestion", original)
    except Exception:
        return original


# ── 重置所有 session state ─────────────────────────────────────
def _reset():
    keys = ["phase", "phase1_result", "essay", "topic",
            "p2_graph", "p2_config", "p2_state",
            "p2_interrupt_type", "p2_sub_action",
            "lo_data", "lo_current", "lo_initialized", "p3_result"]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()


# ============================================================
# 阶段一：输入
# ============================================================
if st.session_state.phase == "input":
    left, right = st.columns([1, 1])
    with left:
        st.subheader("📌 作文题目")
        topic = st.text_input("请输入作文题目")
    with right:
        st.subheader("📝 作文内容")
        essay = st.text_area("请输入作文", height=250)

    if st.button("🚀 开始评分", use_container_width=True):
        if not topic or not essay:
            st.warning("请填写完整信息")
        else:
            with st.spinner("AI 正在分析中..."):
                result = run_phase1(essay=essay, topic=topic)
            st.session_state.phase1_result = result
            st.session_state.essay = essay
            st.session_state.topic = topic
            st.session_state.phase = "phase1_done"
            st.rerun()


# ============================================================
# 阶段一：结果
# ============================================================
elif st.session_state.phase == "phase1_done":
    result = st.session_state.phase1_result
    st.success("✅ 评分完成")
    st.subheader("📄 学生报告")
    st.markdown(f'<div class="essay-box">{result["student_report"]}</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            label="📥 下载报告（TXT）",
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
                label="📊 下载评分数据（Excel）",
                data=f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with st.expander("🔍 查看详细评分数据"):
        st.json(result["backend_data"])

    st.divider()
    if st.button("✏️ 进入阶段二：智能体批阅", use_container_width=True):
        checkpointer = MemorySaver()
        graph = build_phase2_graph(checkpointer=checkpointer)
        p2_config = {"configurable": {"thread_id": "streamlit_session"}}
        st.session_state.p2_graph = graph
        st.session_state.p2_config = p2_config

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
            "sentence_suggestions_batch": None,
            "low_order_decisions_raw": None,
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
        with st.spinner("AI 正在生成修改草稿..."):
            _invoke_p2(initial_state)


# ============================================================
# 阶段二：运行中
# ============================================================
elif st.session_state.phase == "phase2_running":
    state = st.session_state.p2_state
    interrupts = state.get("__interrupt__", [])
    if not interrupts:
        st.session_state.phase = "phase2_done"
        st.rerun()

    interrupt_type = st.session_state.p2_interrupt_type
    sub_action = st.session_state.p2_sub_action

    # ── 高阶修改 ──────────────────────────────────────────────
    if interrupt_type == "high_order":
        iteration = state.get("high_order_iteration", 0)
        v2 = state.get("v2_draft", "")
        summary = state.get("high_order_change_summary") or []

        st.subheader(f"✏️ 高阶修改{'（第 ' + str(iteration) + ' 次调整）' if iteration > 0 else ''}")

        # 对话历史
        history = state.get("high_order_history") or []
        if len(history) > 1:
            with st.expander("📜 对话历史（本轮修改记录）"):
                for i, h in enumerate(history[:-1]):
                    st.markdown(f'<div class="history-box"><b>第 {i+1} 轮：</b><br>{h[:400]}{"..." if len(h) > 400 else ""}</div>',
                                unsafe_allow_html=True)
                    st.write("")

        left_col, right_col = st.columns([3, 2])
        with left_col:
            st.markdown("**📄 修改后的文章**")
            st.markdown(f'<div class="essay-box">{v2}</div>', unsafe_allow_html=True)
        with right_col:
            st.markdown("**📝 主要修改点**")
            changes_text = "\n".join(f"• {s}" for s in summary) if summary else "暂无修改说明"
            st.markdown(f'<div class="change-box">{changes_text}</div>', unsafe_allow_html=True)

        st.divider()

        if sub_action is None:
            st.markdown("**请选择操作：**")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("✅ 接受此版本", use_container_width=True):
                    with st.spinner("AI 处理中..."):
                        _invoke_p2(Command(resume="accept"))
            with c2:
                if st.button("💬 向AI提出修改意见", use_container_width=True):
                    st.session_state.p2_sub_action = "request_changes"
                    st.rerun()
            with c3:
                if st.button("✍️ 提交自己的版本", use_container_width=True):
                    st.session_state.p2_sub_action = "self_edit"
                    st.rerun()

        elif sub_action == "request_changes":
            st.markdown("**请描述你的修改要求：**")
            user_req = st.text_area("修改意见", height=100, key="high_req_input")
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("返回", use_container_width=True):
                    st.session_state.p2_sub_action = None
                    st.rerun()
            with c2:
                if st.button("📤 发送给AI", use_container_width=True):
                    if user_req.strip():
                        with st.spinner("AI 正在重新生成..."):
                            _invoke_p2(Command(resume=user_req.strip()))
                    else:
                        st.warning("请输入修改意见")

        elif sub_action == "self_edit":
            st.markdown("**请输入你自己修改后的完整文章：**")
            self_text = st.text_area("自己的版本", height=300, key="high_self_input", value=v2)
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("返回", use_container_width=True):
                    st.session_state.p2_sub_action = None
                    st.rerun()
            with c2:
                if st.button("🤖 让AI基于此版本继续优化", use_container_width=True):
                    if self_text.strip():
                        with st.spinner("AI 处理中..."):
                            _invoke_p2(Command(resume=f"self_edit_then_ai|||{self_text.strip()}"))
                    else:
                        st.warning("请输入文章")
            with c3:
                if st.button("✅ 直接作为定稿提交", use_container_width=True):
                    if self_text.strip():
                        with st.spinner("处理中..."):
                            _invoke_p2(Command(resume=f"self_edit_final|||{self_text.strip()}"))
                    else:
                        st.warning("请输入文章")

    # ── 高阶自编辑（第二次中断）────────────────────────────────
    elif interrupt_type == "self_edit_high":
        st.subheader("✍️ 输入自己修改的文章")
        self_text = st.text_area("自己的版本", height=300, key="self_edit_high_input")
        if st.button("✅ 提交", use_container_width=True):
            if self_text.strip():
                with st.spinner("处理中..."):
                    _invoke_p2(Command(resume=self_text.strip()))
            else:
                st.warning("请输入文章")

    # ── 低阶批量修改（带前后跳导航）────────────────────────────
    elif interrupt_type == "low_order_nav":
        # 初始化批量数据
        if not st.session_state.lo_initialized:
            suggestions = state.get("sentence_suggestions_batch") or []
            st.session_state.lo_data = [
                {
                    "index": s["index"],
                    "original": s["original"],
                    "suggestion": s["suggestion"],
                    "revision_type": s["revision_type"],
                    "explanation": s.get("explanation", ""),
                    "current_suggestion": s["suggestion"],
                    "alt_suggestions": [],
                    # 无需修改的句子自动预确认
                    "action": "no_change" if s["revision_type"] == "none" else None,
                    "final": s["original"] if s["revision_type"] == "none" else None,
                    "annotation": "",
                    "decided": s["revision_type"] == "none",
                }
                for s in suggestions
            ]
            st.session_state.lo_current = 0
            st.session_state.lo_initialized = True

        lo_data = st.session_state.lo_data
        total = len(lo_data)
        cur_idx = st.session_state.lo_current
        cur = lo_data[cur_idx]
        decided_count = sum(1 for d in lo_data if d["decided"])

        # 进度 & 标题
        st.subheader("✂️ 低阶修改（逐句确认）")
        st.progress(decided_count / total if total > 0 else 0,
                    text=f"已决定：{decided_count}/{total} 句")

        # 导航栏（数字跳转）
        st.markdown(f"<center><b>第 {cur_idx + 1} / {total} 句</b></center>",
                    unsafe_allow_html=True)
        jump = st.number_input("跳到第…句", min_value=1, max_value=total,
                               value=cur_idx + 1, step=1, key="jump_input",
                               label_visibility="visible")
        if int(jump) - 1 != cur_idx:
            st.session_state.lo_current = int(jump) - 1
            st.session_state.p2_sub_action = None
            st.rerun()

        st.divider()

        # 对话历史（本句的替代方案记录）
        if cur["alt_suggestions"]:
            with st.expander(f"📜 本句对话历史（共 {len(cur['alt_suggestions'])} 条替代方案）"):
                st.markdown(f'<div class="history-box"><b>初始 AI 建议：</b> {cur["suggestion"]}</div>',
                            unsafe_allow_html=True)
                for i, alt in enumerate(cur["alt_suggestions"]):
                    st.markdown(f'<div class="history-box"><b>替代方案 {i+1}：</b> {alt}</div>',
                                unsafe_allow_html=True)
                    st.write("")

        # 原句 & 当前建议
        type_map = {
            "grammar": "语法", "vocabulary": "词汇",
            "syntax": "句式", "cohesion": "衔接", "none": "无需修改",
        }
        type_zh = type_map.get(cur["revision_type"], cur["revision_type"])

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("**原句**")
            st.markdown(f'<div class="prompt-box">{cur["original"]}</div>', unsafe_allow_html=True)
        with col_r:
            st.markdown(
                f"**AI 建议** &nbsp;<span style='background:#e8f5e9;padding:2px 8px;"
                f"border-radius:4px;font-size:13px;'>{type_zh}</span>",
                unsafe_allow_html=True)
            if cur["revision_type"] == "none":
                st.markdown('<div class="change-box">✅ 此句无需修改</div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    f'<div class="change-box">{cur["current_suggestion"]}</div>',
                    unsafe_allow_html=True)
            if cur.get("explanation"):
                st.caption(f"说明：{cur['explanation']}")

        # 当前决策状态提示
        if cur["decided"]:
            action_label = {
                "accept": "✅ 已接受 AI 建议",
                "ignore": "⏭️ 已忽略 AI 建议（保留原句）",
                "self_edit": "✍️ 已自行修改",
                "no_change": "✅ 无需修改（已自动确认）",
            }.get(cur["action"], "已决定")
            st.info(f"{action_label}　最终版本：{cur['final']}")

        st.divider()

        # ── 操作区 ──────────────────────────────────────────
        if cur["revision_type"] == "none":
            # 自动确认，允许覆写
            st.success("AI 认为此句无需修改，已自动确认。")
            if st.checkbox("我想对此句进行修改", key=f"override_{cur_idx}"):
                self_sent = st.text_input(
                    "输入你的版本", value=cur["original"], key=f"override_text_{cur_idx}")
                if st.button("💾 保存修改", key=f"override_save_{cur_idx}"):
                    lo_data[cur_idx].update({
                        "action": "self_edit",
                        "final": self_sent,
                        "decided": True,
                    })
                    st.session_state.lo_data = lo_data
                    st.rerun()
        else:
            if sub_action is None:
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    if st.button("✅ 接受建议", key=f"accept_{cur_idx}",
                                 use_container_width=True, type="primary"):
                        lo_data[cur_idx].update({
                            "action": "accept",
                            "final": cur["current_suggestion"],
                            "decided": True,
                        })
                        st.session_state.lo_data = lo_data
                        # 自动跳下一句
                        if cur_idx < total - 1:
                            st.session_state.lo_current += 1
                        st.rerun()
                with c2:
                    if st.button("⏭️ 忽略建议", key=f"ignore_{cur_idx}",
                                 use_container_width=True):
                        lo_data[cur_idx].update({
                            "action": "ignore",
                            "final": cur["original"],
                            "decided": True,
                        })
                        st.session_state.lo_data = lo_data
                        if cur_idx < total - 1:
                            st.session_state.lo_current += 1
                        st.rerun()
                with c3:
                    if st.button("🔄 换一种改法", key=f"alt_{cur_idx}",
                                 use_container_width=True):
                        st.session_state.p2_sub_action = "request_alt"
                        st.rerun()
                with c4:
                    if st.button("✍️ 自己修改", key=f"self_{cur_idx}",
                                 use_container_width=True):
                        st.session_state.p2_sub_action = "self_sentence"
                        st.rerun()

            elif sub_action == "request_alt":
                alt_req = st.text_input("描述修改要求（可留空让 AI 自行生成）",
                                        key=f"alt_req_{cur_idx}")
                c1, c2 = st.columns([1, 4])
                with c1:
                    if st.button("取消", key=f"alt_cancel_{cur_idx}"):
                        st.session_state.p2_sub_action = None
                        st.rerun()
                with c2:
                    if st.button("🤖 生成替代方案", key=f"gen_alt_{cur_idx}",
                                 use_container_width=True):
                        with st.spinner("AI 生成替代方案中..."):
                            new_sug = _get_alternative(
                                cur["original"], cur["current_suggestion"],
                                alt_req, cur["alt_suggestions"])
                        lo_data[cur_idx]["alt_suggestions"].append(new_sug)
                        lo_data[cur_idx]["current_suggestion"] = new_sug
                        st.session_state.lo_data = lo_data
                        st.session_state.p2_sub_action = None
                        st.rerun()

            elif sub_action == "self_sentence":
                self_sent = st.text_input(
                    "输入你自己的版本", value=cur["original"],
                    key=f"self_sent_{cur_idx}")
                c1, c2 = st.columns([1, 4])
                with c1:
                    if st.button("取消", key=f"self_cancel_{cur_idx}"):
                        st.session_state.p2_sub_action = None
                        st.rerun()
                with c2:
                    if st.button("✅ 保存", key=f"save_self_{cur_idx}",
                                 use_container_width=True, type="primary"):
                        lo_data[cur_idx].update({
                            "action": "self_edit",
                            "final": self_sent,
                            "decided": True,
                        })
                        st.session_state.lo_data = lo_data
                        st.session_state.p2_sub_action = None
                        if cur_idx < total - 1:
                            st.session_state.lo_current += 1
                        st.rerun()

        # 批注（选填）
        new_anno = st.text_input(
            "📝 批注（选填，可填写你对此句修改的想法）",
            value=cur.get("annotation", ""),
            key=f"anno_{cur_idx}",
            placeholder="例如：我觉得 AI 的修改更流畅，所以接受了…")
        if new_anno != cur.get("annotation", ""):
            lo_data[cur_idx]["annotation"] = new_anno
            st.session_state.lo_data = lo_data

        st.divider()

        # 所有句子概览（纯文本，无跳转按钮）
        with st.expander("📋 所有句子概览"):
            for i, d in enumerate(lo_data):
                icon = "✅" if d["decided"] else "⏳"
                label = {
                    "accept": "接受", "ignore": "忽略", "self_edit": "自改", "no_change": "无需改"
                }.get(d.get("action"), "未决定")
                st.markdown(f"{icon} **{i+1}.** {d['original'][:60]}… `{label}`")

        # 提交按钮
        undecided = [i for i, d in enumerate(lo_data) if not d["decided"]]
        if undecided:
            st.warning(f"还有 {len(undecided)} 句未决定（第 "
                       f"{', '.join(str(i+1) for i in undecided[:5])}{'…' if len(undecided) > 5 else ''} 句），"
                       "提交时将自动保留原句。")

        if st.button("✅ 完成全部修改，提交", use_container_width=True, type="primary"):
            # 未决定的句子自动设为 keep_original
            for i in undecided:
                lo_data[i].update({"action": "keep_original",
                                   "final": lo_data[i]["original"],
                                   "decided": True})
            decisions_payload = {
                "decisions": [
                    {
                        "index": d["index"],
                        "action": d["action"],
                        "final": d["final"],
                        "annotation": d.get("annotation", ""),
                        "alt_history": d.get("alt_suggestions", []),
                    }
                    for d in lo_data
                ]
            }
            st.session_state.lo_initialized = False
            with st.spinner("AI 正在分析修改行为，请稍候…（约1-2分钟）"):
                _invoke_p2(Command(resume=json.dumps(decisions_payload, ensure_ascii=False)))


# ============================================================
# 阶段二：完成
# ============================================================
elif st.session_state.phase == "phase2_done":
    result = st.session_state.p2_state
    st.success("✅ 批阅完成")

    # V6 文章
    st.subheader("📄 V6 最终作文")
    v6 = result.get("v6_essay", "")
    st.markdown(f'<div class="essay-box">{v6}</div>', unsafe_allow_html=True)
    st.download_button(
        label="📥 下载 V6 作文（TXT）",
        data=v6,
        file_name="v6_essay.txt",
        mime="text/plain",
        use_container_width=True,
    )

    st.divider()

    # 总的修改批注
    st.subheader("📋 总的修改批注")
    events = result.get("revision_events") or []
    decisions = result.get("sentence_decisions") or []

    high_events = [e for e in events if e.get("phase") == "high_order"]
    low_events = [e for e in events if e.get("phase") == "low_order"]

    tab1, tab2, tab3 = st.tabs(["高阶修改记录", "低阶修改逐句记录", "统计摘要"])

    with tab1:
        if high_events:
            for idx_e, e in enumerate(high_events):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.markdown(f"**修改策略：** {e.get('modification_strategy', '')}")
                        st.markdown(
                            f"**修改焦点：** {', '.join(e.get('modification_focus') or [])} | "
                            f"**修改类型：** {', '.join(e.get('modification_type') or [])}")
                    with c2:
                        st.markdown(f"**反馈吸收：**")
                        st.markdown(f"`{e.get('feedback_absorption', '')}`")
                    if e.get("student_annotation"):
                        st.info(f"📝 学生批注：{e['student_annotation']}")
                    else:
                        st.caption("（无批注）")
        else:
            st.info("无高阶修改记录")

    with tab2:
        annotated = [d for d in decisions if (d["revision_event"].get("student_annotation") or "").strip()]
        st.caption(f"共 {len(decisions)} 句，其中 {len(annotated)} 句有学生批注")
        for d in sorted(decisions, key=lambda x: x["index"]):
            if d["decision"] == "no_change_needed":
                continue
            decision_label = {
                "accept": "✅ 接受", "keep_original": "↩️ 保留原句",
                "ignored": "⏭️ 忽略", "self_submitted": "✍️ 自行修改",
                "alternative_accepted": "🔄 接受替代方案",
            }.get(d["decision"], d["decision"])
            with st.expander(
                    f"{decision_label} 第 {d['index']+1} 句：{d['original'][:60]}…"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown("**原句**")
                    st.markdown(f'<div class="prompt-box">{d["original"]}</div>',
                                unsafe_allow_html=True)
                with col2:
                    st.markdown("**AI 建议**")
                    st.markdown(f'<div class="change-box">{d["ai_suggestion"]}</div>',
                                unsafe_allow_html=True)
                with col3:
                    st.markdown("**最终版本**")
                    st.markdown(f'<div class="decided-box">{d["final"]}</div>',
                                unsafe_allow_html=True)
                st.markdown(
                    f"**修改类型：** `{d['revision_type']}` | "
                    f"**迭代次数：** {d['iteration_count']}")
                ann = (d["revision_event"].get("student_annotation") or "").strip()
                if ann:
                    st.info(f"📝 学生批注：{ann}")

    with tab3:
        if events:
            strategy_cnt: dict = {}
            absorption_cnt: dict = {}
            for e in events:
                s = e.get("modification_strategy", "未知")
                strategy_cnt[s] = strategy_cnt.get(s, 0) + 1
                a = e.get("feedback_absorption", "未知")
                absorption_cnt[a] = absorption_cnt.get(a, 0) + 1

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("总修改事件", len(events))
                st.metric("高阶修改", len(high_events))
                st.metric("低阶修改", len(low_events))
            with c2:
                st.markdown("**修改策略分布**")
                for k, v in strategy_cnt.items():
                    st.markdown(f"- {k}: **{v}** 次")
            with c3:
                st.markdown("**反馈吸收分布**")
                for k, v in absorption_cnt.items():
                    st.markdown(f"- {k}: **{v}** 次")

    st.divider()

    # 阶段三入口
    if st.button("📊 进入阶段三：写作反馈素养评估", use_container_width=True, type="primary"):
        st.session_state.phase = "phase3_running"
        st.rerun()

    if st.button("🔄 重新开始", use_container_width=True):
        _reset()


# ============================================================
# 阶段三：运行中
# ============================================================
elif st.session_state.phase == "phase3_running":
    from phase3.graph import build_phase3_graph

    state = st.session_state.p2_state
    with st.spinner("AI 正在分析你的写作反馈素养…（约1分钟）"):
        graph = build_phase3_graph()
        p3_input = {
            "v1_essay": st.session_state.essay,
            "v6_essay": state.get("v6_essay", ""),
            "topic": st.session_state.topic,
            "revision_events": state.get("revision_events") or [],
            "sentence_decisions": state.get("sentence_decisions") or [],
            "high_order_history": state.get("high_order_history") or [],
            "modification_stats": None,
            "literacy_report": None,
            "literacy_data": None,
            "phase3_complete": False,
        }
        p3_result = graph.invoke(p3_input)

    st.session_state.p3_result = p3_result
    st.session_state.phase = "phase3_done"
    st.rerun()


# ============================================================
# 阶段三：完成
# ============================================================
elif st.session_state.phase == "phase3_done":
    p3 = st.session_state.p3_result
    st.success("✅ 写作反馈素养评估完成")

    # 素养报告
    st.subheader("📊 写作反馈素养评估报告")
    report = p3.get("literacy_report", "")
    st.markdown(report)

    st.download_button(
        label="📥 下载素养报告（TXT）",
        data=report,
        file_name="literacy_report.txt",
        mime="text/plain",
        use_container_width=True,
    )

    # 统计数据
    stats = p3.get("modification_stats") or {}
    if stats:
        st.divider()
        st.subheader("📈 修改行为统计")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("总修改事件", stats.get("total_events", 0))
            st.metric("高阶修改", stats.get("total_high_order", 0))
            st.metric("低阶修改", stats.get("total_low_order", 0))
            st.metric("高阶批注率",
                      f"{stats.get('high_order_annotation_rate', 0)*100:.0f}%")
        with c2:
            st.markdown("**修改策略分布**")
            for k, v in (stats.get("modification_strategy") or {}).items():
                st.markdown(f"- {k}: **{v}** 次")
        with c3:
            st.markdown("**反馈吸收分布**")
            for k, v in (stats.get("feedback_absorption") or {}).items():
                st.markdown(f"- {k}: **{v}** 次")

    # 研究组后台数据
    with st.expander("🔬 研究组数据（详细标注记录）"):
        st.json({
            "literacy_data": p3.get("literacy_data"),
            "modification_stats": stats,
            "revision_events": (st.session_state.p2_state or {}).get("revision_events") or [],
        })

    st.divider()
    if st.button("🔄 重新开始", use_container_width=True):
        _reset()
