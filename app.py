import streamlit as st
from run_phase1 import run_phase1
import json
from datetime import datetime
from phase1.excel_exporter import export_to_excel

# ======================
# 页面配置（必须最前）
# ======================
st.set_page_config(
    page_title="作文评分系统",
    page_icon="🧠",   # 左上角图标（可以换成本地图片）
    layout="wide"
)

# ======================
# 自定义CSS（美化核心）
# ======================
st.markdown("""
<style>
.main {
    padding: 2rem;
}
.stButton>button {
    width: 100%;
    border-radius: 10px;
    height: 3em;
    font-size: 16px;
}
.block-container {
    padding-top: 2rem;
}
</style>
""", unsafe_allow_html=True)

# ======================
# 标题区（带图标）
# ======================
col1, col2 = st.columns([1, 8])

with col1:
    st.image("logo.png", width=150)

with col2:
    st.title("中英文智能体 · 作文评分系统")
    st.caption("AI Essay Evaluation System")

st.divider()

# ======================
# 输入区（左右布局）
# ======================
left, right = st.columns([1, 1])

with left:
    st.subheader("📌 作文题目")
    topic = st.text_input("请输入作文题目")

with right:
    st.subheader("📝 作文内容")
    essay = st.text_area("请输入你的作文", height=250)

# ======================
# 按钮
# ======================
if st.button("🚀 开始评分"):

    if not topic or not essay:
        st.warning("⚠️ 请填写完整信息")
    else:
        with st.spinner("⏳ AI 正在分析中..."):

            result = run_phase1(essay=essay, topic=topic)

        st.success("✅ 评分完成")

        # ======================
        # 输出区（卡片化）
        # ======================
        st.subheader("📄 学生报告")

        st.markdown(f"""
        <div style="
            background-color:#f8f9fa;
            color:#212529;
            padding:20px;
            border-radius:10px;
            border:1px solid #ddd;
            white-space:pre-wrap;
        ">
{result["student_report"]}
        </div>
        """, unsafe_allow_html=True)

        # ======================
        # 下载 TXT
        # ======================
        report_text = result["student_report"]

        st.download_button(
            label="📥 下载报告（TXT）",
            data=report_text,
            file_name="report.txt",
            mime="text/plain"
        )

        # ======================
        # 下载 Excel
        # ======================
        backend_data = result["backend_data"]

        # 临时生成 Excel 文件
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        export_to_excel(backend_data, filepath=filename)

        with open(filename, "rb") as f:
            st.download_button(
                label="📊 下载评分数据（Excel）",
                data=f,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # ======================
        # 详细数据
        # ======================
        with st.expander("🔍 查看详细评分数据"):
            st.json(backend_data)