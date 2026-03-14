from typing import TypedDict, Optional


class DimensionResult(TypedDict):
    """单个维度的评分结果"""
    sub_scores: list          # 各子描述语得分（0-4 分制）
    final_score: float        # 最终得分（0-5 分制，由公式计算）
    strengths: str            # 强项（呈现给学生）
    weaknesses: str           # 弱项（呈现给学生）


class Phase1State(TypedDict):
    """阶段一完整状态"""
    # 输入
    essay: str                # 学生作文
    topic: str                # 作文题目

    # 四六级总体打分
    cet4_score: Optional[int]       # 四级总分（0-15）
    cet4_band: Optional[str]        # 四级档位描述
    cet4_rationale: Optional[str]   # 四级打分理由

    cet6_score: Optional[int]       # 六级总分（0-15）
    cet6_band: Optional[str]        # 六级档位描述
    cet6_rationale: Optional[str]   # 六级打分理由

    # 六维度诊断反馈
    argumentation: Optional[DimensionResult]   # 论证能力
    discourse: Optional[DimensionResult]       # 语篇能力
    convention: Optional[DimensionResult]      # 书写规范
    vocabulary: Optional[DimensionResult]      # 词汇
    grammar: Optional[DimensionResult]         # 语法
    syntax: Optional[DimensionResult]          # 句法

    # 输出
    student_report: Optional[str]    # 呈现给学生的完整报告
    backend_data: Optional[dict]     # 留存给研究组的数据
