import os
from dotenv import load_dotenv

load_dotenv()

# ── API 提供商配置 ────────────────────────────────────────────
# 支持两种模式（在 .env 中通过 API_PROVIDER 切换）：
#   anthropic   → 使用 Anthropic 官方 API
#   siliconflow → 使用硅基流动 OpenAI 兼容 API（开发阶段推荐）
API_PROVIDER = os.getenv("API_PROVIDER", "siliconflow")

# ── 硅基流动配置 ──────────────────────────────────────────────
SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
# 硅基流动推荐模型（支持中文、指令跟随强）：
#   Qwen/Qwen2.5-72B-Instruct         （旗舰，效果好）
#   Qwen/Qwen2.5-32B-Instruct         （平衡）
#   deepseek-ai/DeepSeek-V3           （推理强）
SILICONFLOW_MODEL = os.getenv("SILICONFLOW_MODEL", "Qwen/Qwen3-30B-A3B-Instruct-2507")

# ── Anthropic 配置 ────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

# ── 统一暴露给 nodes.py 使用 ──────────────────────────────────
if API_PROVIDER == "siliconflow":
    MODEL_NAME = SILICONFLOW_MODEL
    if not SILICONFLOW_API_KEY:
        import warnings
        warnings.warn("未检测到 SILICONFLOW_API_KEY，请在 .env 文件中配置。")
else:
    MODEL_NAME = ANTHROPIC_MODEL
    if not ANTHROPIC_API_KEY:
        import warnings
        warnings.warn("未检测到 ANTHROPIC_API_KEY，请在 .env 文件中配置。")
