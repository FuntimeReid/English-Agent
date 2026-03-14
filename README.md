# English Agent — 英语写作智能体辅助系统

基于 [LangGraph](https://github.com/langchain-ai/langgraph) 框架构建的英语写作评分与诊断系统，面向大学英语四六级写作教学场景。

---

## 功能概览

### 阶段一：写作评分与诊断（已实现）

- **四六级总体评分**：按四级和六级两套标准分别打分（0–15 分，共 5 档）
- **六维度诊断反馈**：从论证、语篇、书写规范、词汇、语法、句法六个维度对作文进行细粒度分析
- **详细评分表格**：每个维度下所有子描述语的逐条得分记录，导出为格式化 Excel
- **评分一致性保证**：相同作文多次提交返回相同结果（MD5 缓存 + temperature=0）

---

## 项目结构

```
English Agent/
├── config.py                    # API 配置（支持 siliconflow / anthropic 切换）
├── .env.example                 # 环境变量模板
├── run_phase1.py                # 阶段一运行入口
└── phase1/
    ├── state.py                 # LangGraph 状态定义
    ├── prompts.py               # 评分提示词（四六级 + 六维度）
    ├── descriptors.py           # 六维度完整描述语与评分细则
    ├── nodes.py                 # 三个节点：总体打分 / 六维度打分 / 生成报告
    ├── graph.py                 # LangGraph 图定义
    └── excel_exporter.py        # 格式化 Excel 导出
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install langgraph langchain langchain-openai langchain-anthropic openpyxl python-dotenv
```

### 2. 配置 API Key

复制环境变量模板并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env`：

```
API_PROVIDER=siliconflow
SILICONFLOW_API_KEY=你的硅基流动API Key
```

如需使用 Anthropic Claude，将 `API_PROVIDER` 改为 `anthropic` 并填入 `ANTHROPIC_API_KEY`。

### 3. 修改待评作文

打开 `run_phase1.py`，修改文件顶部的 `SAMPLE_TOPIC` 和 `SAMPLE_ESSAY` 变量：

```python
SAMPLE_TOPIC = "作文题目"

SAMPLE_ESSAY = """
你的作文内容...
"""
```

### 4. 运行评分

```bash
python run_phase1.py
```

---

## 输出结果

| 输出文件 | 说明 |
|---|---|
| 终端打印 | 学生报告 + 后台 JSON 数据 |
| `report.txt` | 完整报告文本（含后台数据） |
| `report_时间戳.xlsx` | 格式化 Excel，含两个 Sheet |

**Excel 内容：**
- **总览 Sheet**：四六级得分 + 档位 + 评分说明；六维度最终得分 + 强项/弱项
- **详细评分记录 Sheet**：每个维度下所有子描述语的维度 / 子维度 / 描述语全文 / 得分，按维度分组、色彩标注

---

## 评分体系说明

### 四六级总体评分

| 档位 | 四级得分 | 六级得分 |
|---|---|---|
| 优秀 | 13–15 | 13–15 |
| 良好 | 10–12 | 10–12 |
| 中等 | 7–9 | 7–9 |
| 及格 | 4–6 | 4–6 |
| 较差 | 0–3 | 0–3 |

### 六维度评分

| 维度 | 子项数 |
|---|---|
| 论证能力 | 14 |
| 语篇能力 | 8 |
| 书写规范 | 4 |
| 词汇 | 8 |
| 语法 | 4 |
| 句法 | 4 |

- 每条子描述语独立打分：**0–4 分**
- 维度最终得分公式：`(各子项总分 / 子项数) / 4 × 5`，范围 **0–5 分**
- 各维度独立评分，互不影响

---

## API 提供商配置

在 `.env` 中设置 `API_PROVIDER`：

| 值 | 说明 | 所需变量 |
|---|---|---|
| `siliconflow`（默认） | 硅基流动，支持 Qwen 等国内模型 | `SILICONFLOW_API_KEY` |
| `anthropic` | Anthropic Claude | `ANTHROPIC_API_KEY` |

默认模型：`Qwen/Qwen3-30B-A3B-Instruct-2507`（可在 `.env` 中通过 `SILICONFLOW_MODEL` 修改）

---

## 注意事项

- `.env` 文件包含 API Key，**请勿提交到版本控制系统**（已在 `.gitignore` 中排除）
- 运行时若 Excel 文件在 Excel 中打开，不会报错（文件名含时间戳，每次生成新文件）
- Python 3.14 + pydantic v1 环境下会有 `UserWarning`，不影响功能正常运行
