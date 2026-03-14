"""
阶段一演示脚本
用法：python run_phase1.py
"""

import hashlib
import json
import os
from datetime import datetime

from phase1.graph import phase1_graph
from phase1.excel_exporter import export_to_excel

# ============================================================
# 示例作文（来自文档中的样例）
# ============================================================
SAMPLE_TOPIC = """For this part, you are allowed 30 minutes to write a short essay entitled Should the University Campus Be Open to Tourists?"""

SAMPLE_ESSAY = """Nowadays, most of the universities are open to the public. And the famous universities are gradually becoming the new tourism attractions. So a question arise. Should the university campus be open to tourists? People have different opinions.
Some people think that the university campus symblize the literature of the country. The visit to university campuses can give the tourists a general idea of the literature of the country. But other people think that if the university campus are open to tourists, the peace envirnment for the university students to study will be ruined. University campus is the holy place for studying, So they shouldn't be open to tourists.
I think both ideas have its own reasons and the best answer to the question is that the university campus can be open to tourists on Saturday and Sunday or limit the amount of the tourists. In this way, not only the tourists can visit the famous university campuses but also won't the peace environment of the campuses be destroyed.
"""

# ============================================================
# 缓存工具
# ============================================================
CACHE_DIR = "cache"


def _cache_key(essay: str, topic: str) -> str:
    content = f"{topic}|||{essay}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def _load_cache(key: str) -> dict | None:
    path = os.path.join(CACHE_DIR, f"{key}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_cache(key: str, result: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{key}.json")
    # State 中部分值（如 DimensionResult TypedDict）可能含不可序列化对象，
    # 只缓存两个输出字段即可
    cacheable = {
        "student_report": result["student_report"],
        "backend_data":   result["backend_data"],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cacheable, f, ensure_ascii=False, indent=2)


# ============================================================
# 主流程
# ============================================================
def run_phase1(essay: str, topic: str, use_cache: bool = True) -> dict:
    """
    运行阶段一评分流程。

    参数:
        essay:     学生作文文本
        topic:     作文题目
        use_cache: 是否启用缓存（默认开启）
                   同一篇文章重复提交时直接返回首次结果，保证评分一致性

    返回:
        包含所有评分结果的状态字典
    """
    key = _cache_key(essay, topic)

    if use_cache:
        cached = _load_cache(key)
        if cached:
            print(f"命中缓存（key: {key[:8]}...），直接返回已有评分结果。\n")
            return cached

    initial_state = {
        "essay": essay,
        "topic": topic,
        "cet4_score": None, "cet4_band": None, "cet4_rationale": None,
        "cet6_score": None, "cet6_band": None, "cet6_rationale": None,
        "argumentation": None, "discourse": None, "convention": None,
        "vocabulary":   None, "grammar":   None, "syntax":      None,
        "student_report": None, "backend_data": None,
    }

    print("正在评分中，请稍候...\n")
    result = phase1_graph.invoke(initial_state)

    if use_cache:
        _save_cache(key, result)

    return result


def main():
    result = run_phase1(essay=SAMPLE_ESSAY, topic=SAMPLE_TOPIC)

    student_report = result["student_report"]
    backend_data   = result["backend_data"]
    backend_json   = json.dumps(backend_data, ensure_ascii=False, indent=2)

    # 终端输出
    print(student_report)
    print("\n【后台数据（研究组）】")
    print(backend_json)

    # 保存 txt
    report_content = student_report + "\n\n【后台数据（研究组）】\n" + backend_json
    with open("report.txt", "w", encoding="utf-8") as f:
        f.write(report_content)
    print("\n评价结果已保存至 report.txt")

    # 导出 Excel（文件名含时间戳，避免文件被占用时报错）
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = f"report_{ts}.xlsx"
    export_to_excel(backend_data, filepath=excel_path)


if __name__ == "__main__":
    main()
