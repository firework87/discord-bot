"""AI 呼叫邏輯：DeepSeek 優先，OpenRouter 備用"""

import asyncio
from config import MODEL_CLIENTS, FREE_MODELS, executor


def _ask_ai_sync(messages, model_index=0):
    """同步版本：依序嘗試 DeepSeek → OpenRouter 模型"""
    if model_index >= len(FREE_MODELS):
        return "❌ 所有模型都暫時無法使用，請稍後再試。"

    model = FREE_MODELS[model_index]
    client = MODEL_CLIENTS.get(model)

    if client is None:
        # 模型沒有對應的客戶端，跳過
        return _ask_ai_sync(messages, model_index + 1)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1000,
        )
        return response.choices[0].message.content

    except Exception as e:
        error_msg = str(e)
        print(f"⚠️ {model} 失敗：{error_msg[:150]}")

        # 任何錯誤都嘗試下一個模型
        return _ask_ai_sync(messages, model_index + 1)


async def ask_ai(messages):
    """非同步版本（不阻塞 Discord）"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, _ask_ai_sync, messages)


async def safe_typing(ctx):
    """安全地顯示輸入中狀態"""
    try:
        await ctx.trigger_typing()
    except Exception:
        pass


async def send_long_message(ctx, text):
    """安全發送長訊息，自動分段"""
    for i in range(0, len(text), 1900):
        await ctx.send(text[i:i+1900])
