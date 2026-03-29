# English Agent — 英语写作智能体辅助系统

基于 [LangGraph](https://github.com/langchain-ai/langgraph) + [Streamlit](https://streamlit.io) 构建的英语写作评分、智能体批阅与写作反馈素养评估系统，面向大学英语四六级写作教学场景。

---

## 功能概览

### 阶段一：写作评分与诊断

- **四六级总体评分**：按四级和六级两套标准分别打分（0–15 分，共 5 档）
- **六维度诊断反馈**：从论证、语篇、书写规范、词汇、语法、句法六个维度细粒度分析
- **详细评分表格**：每条子描述语逐项得分，导出为格式化 Excel
- **评分一致性保证**：相同作文多次提交返回相同结果（MD5 缓存 + temperature=0）

### 阶段二：智能体批阅与修改

- **高阶修改（篇章级）**：AI 根据论证与语篇弱点生成修改草稿（V2），支持多轮对话提意见或自行修改
- **低阶修改（句子级）**：AI 批量为所有句子生成语法/词汇/句式/衔接建议，学生逐句确认
  - ← → 前后跳转与数字直接跳转
  - 每句可查看完整对话历史（AI 建议 + 替代方案记录）
  - 四种操作：✅ 接受 / ⏭️ 忽略 / 🔄 换一种改法 / ✍️ 自己修改
  - 可为每句添加学生批注
- **总的修改批注**：完成后展示三标签页汇总（高阶记录 / 逐句低阶记录 / 统计摘要）

### 阶段三：写作反馈素养评估

- **修改行为统计**：统计修改策略、反馈吸收方式、修改焦点等频次分布
- **素养评估报告**：基于四维度框架（认知 / 行为 / 情感 / 伦理）生成个性化文字报告
- **研究数据导出**：结构化 JSON 供研究组使用

---

## 项目结构

```
English-Agent/
├── app.py                       # Streamlit 主应用（三阶段一体化 UI）
├── config.py                    # API 配置（siliconflow / anthropic 切换）
├── run_phase1.py                # 阶段一 CLI 运行入口
├── run_phase2.py                # 阶段二 CLI 运行入口
├── run_phase3.py                # 阶段三 CLI 运行入口
├── .env.example                 # 环境变量模板
│
├── phase1/
│   ├── state.py                 # LangGraph 状态定义
│   ├── prompts.py               # 评分提示词（四六级 + 六维度）
│   ├── descriptors.py           # 六维度完整描述语与评分细则
│   ├── nodes.py                 # 节点：总体打分 / 六维度打分 / 生成报告
│   ├── graph.py                 # LangGraph 图定义
│   └── excel_exporter.py        # 格式化 Excel 导出
│
├── phase2/
│   ├── state.py                 # 状态定义（RevisionEvent / SentenceDecision）
│   ├── prompts.py               # 高阶/低阶修改提示词
│   ├── nodes.py                 # 高阶节点 + 批量低阶节点 + 推断节点
│   └── graph.py                 # LangGraph 图（高阶循环 → 批量低阶 → 组装）
│
└── phase3/
    ├── state.py                 # Phase3State TypedDict
    ├── prompts.py               # 素养评估系统提示词（四维度框架）
    ├── nodes.py                 # compute_stats + generate_literacy_report
    └── graph.py                 # 简单线性图（统计 → 报告）
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install streamlit langgraph langchain langchain-openai langchain-anthropic openpyxl python-dotenv
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`：

```
API_PROVIDER=siliconflow
SILICONFLOW_API_KEY=你的硅基流动API Key
```

如需使用 Anthropic Claude：

```
API_PROVIDER=anthropic
ANTHROPIC_API_KEY=你的Claude API Key
```

### 3. 启动 Web 应用（推荐）

```bash
streamlit run app.py
```

浏览器打开后，按照页面引导依次完成三个阶段即可。

### 4. CLI 模式（逐阶运行）

**阶段一**（评分）：

```bash
python run_phase1.py
# 输出：report.txt + report_时间戳.xlsx
```

**阶段二**（批阅）：

```bash
python run_phase2.py
# 交互式终端，按提示输入操作
# 输出：phase2_result.json
```

**阶段三**（素养评估，读取 phase2_result.json）：

```bash
python run_phase3.py
# 输出：phase3_result.json + literacy_report.txt
```

---

## 使用流程（Web 应用）

```
输入作文题目 & 正文
        ↓
  [阶段一] AI 评分 → 查看报告 / 下载 Excel
        ↓
  [阶段二] 高阶修改（多轮对话）
        ↓
  [阶段二] 低阶修改（逐句确认，支持前后跳转）
        ↓
  查看总的修改批注（三标签页）
        ↓
  [阶段三] 写作反馈素养评估报告
```

---

## 输出文件说明

| 文件 | 说明 |
|---|---|
| `report.txt` | 阶段一学生报告（CLI） |
| `report_时间戳.xlsx` | 阶段一评分数据 Excel |
| `phase2_result.json` | 阶段二结果（V1/V4/V6 作文 + 修改事件）|
| `phase3_result.json` | 阶段三结果（素养报告 + 统计数据）|
| `literacy_report.txt` | 素养评估文字报告（CLI） |

---

## 评分体系

### 四六级总体评分

| 档位 | 得分范围 |
|---|---|
| 优秀 | 13–15 |
| 良好 | 10–12 |
| 中等 | 7–9 |
| 及格 | 4–6 |
| 较差 | 0–3 |

### 六维度评分

| 维度 | 子项数 | 得分范围 |
|---|---|---|
| 论证能力 | 14 | 0–5 |
| 语篇能力 | 8 | 0–5 |
| 书写规范 | 4 | 0–5 |
| 词汇 | 8 | 0–5 |
| 语法 | 4 | 0–5 |
| 句法 | 4 | 0–5 |

每条子描述语独立打分（0–4），维度得分公式：`(各子项总分 / 子项数) / 4 × 5`

### 写作反馈素养四维度

| 维度 | 说明 |
|---|---|
| 认知维度 | 是否理解 AI 反馈、能否区分不同反馈来源 |
| 行为维度 | 反馈提示、反馈判断、反馈实施能力 |
| 情感维度 | 对 AI 反馈的情感认同与投入意愿 |
| 伦理维度 | 保持原创性、识别 AI 潜在偏见的能力 |

---

## API 提供商配置

| `API_PROVIDER` | 说明 | 所需变量 |
|---|---|---|
| `siliconflow`（默认） | 硅基流动，支持 Qwen 等国内模型 | `SILICONFLOW_API_KEY` |
| `anthropic` | Anthropic Claude | `ANTHROPIC_API_KEY` |

默认模型可在 `.env` 中通过 `SILICONFLOW_MODEL` / `ANTHROPIC_MODEL` 修改。

---

## 注意事项

- `.env` 包含 API Key，**请勿提交到版本控制**（已在 `.gitignore` 中排除）
- 阶段二低阶修改会为所有句子批量调用 LLM，句子较多时需等待约 30–60 秒
- 阶段三素养报告生成约需 30–60 秒
- CLI 的阶段二（`run_phase2.py`）使用纯文本交互，建议通过 Web 应用体验完整功能
- Python 3.12+ 环境下运行正常；pydantic v1/v2 混用时可能出现 `UserWarning`，不影响功能
