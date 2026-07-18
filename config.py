"""設定檔：環境變數、模型列表、共用常數"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor
import requests
from dotenv import load_dotenv
from openai import OpenAI

# 確保 Windows 終端能正確輸出 UTF-8（含 emoji）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# 載入 .env 環境變數
load_dotenv()

# ========== API 金鑰 ==========
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API")

# ========== 主要模型：DeepSeek ==========
deepseek_client = None
DEEPSEEK_MODELS = []

if DEEPSEEK_API_KEY:
    deepseek_client = OpenAI(
        base_url="https://api.deepseek.com",
        api_key=DEEPSEEK_API_KEY,
    )
    DEEPSEEK_MODELS = ["deepseek-chat", "deepseek-reasoner"]
    print(f"🔷 DeepSeek API 已設定（{len(DEEPSEEK_MODELS)} 個模型）")
else:
    print("⚠️  DEEPSEEK_API 未設定，將直接使用 OpenRouter")

# ========== 備用模型：OpenRouter ==========
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

# ========== 預設備用模型 ==========
DEFAULT_FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "deepseek/deepseek-chat:free",
    "huggingfaceh4/zephyr-7b-beta:free",
]

def get_free_models():
    """從 OpenRouter API 抓取目前可用的免費模型"""
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            timeout=10
        )
        data = resp.json()

        free_models = []
        for m in data.get("data", []):
            model_id = m.get("id", "")
            pricing = m.get("pricing", {})
            is_free = all(
                float(pricing.get(k, 999)) == 0
                for k in ["prompt", "completion", "image", "request"]
            )
            if is_free or ":free" in model_id:
                free_models.append(model_id)

        print(f"✅ 找到 {len(free_models)} 個免費模型")
        for fm in free_models[:5]:
            print(f"   - {fm}")
        return free_models

    except Exception as e:
        print(f"❌ 抓取模型失敗：{e}")
        return []

# 取得免費模型列表
openrouter_models = get_free_models()
if not openrouter_models:
    openrouter_models = DEFAULT_FREE_MODELS
    print("⚠️ 使用 OpenRouter 預設備用模型")

# ========== 合併模型列表（DeepSeek 優先 → OpenRouter 備用）==========
FREE_MODELS = DEEPSEEK_MODELS + openrouter_models

# 模型 → 客戶端對應表
MODEL_CLIENTS = {}
for m in DEEPSEEK_MODELS:
    if deepseek_client:
        MODEL_CLIENTS[m] = deepseek_client
for m in openrouter_models:
    MODEL_CLIENTS[m] = openrouter_client

CURRENT_MODEL = FREE_MODELS[0] if FREE_MODELS else None
print(f"🎯 當前使用模型：{CURRENT_MODEL}")
print(f"   DeepSeek: {len(DEEPSEEK_MODELS)} 個 | OpenRouter: {len(openrouter_models)} 個")

# ========== 共用設定 ==========
DEFAULT_SYSTEM_PROMPT = "你是一個有幫助的助手，用繁體中文回答。"
SESSION_TIMEOUT = 3600  # 1 小時未使用則清除

# 執行緒池（供 AI 呼叫使用）
executor = ThreadPoolExecutor(max_workers=2)
