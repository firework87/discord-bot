"""對話 Session 與提示詞管理"""

import time
from threading import Lock
from config import DEFAULT_SYSTEM_PROMPT, SESSION_TIMEOUT

# ========== 對話 Session ==========
chat_sessions = {}
chat_sessions_lock = Lock()


def cleanup_old_sessions():
    """清除過期的對話 session，避免記憶體洩漏"""
    now = time.time()
    with chat_sessions_lock:
        expired = [
            uid for uid, sess in chat_sessions.items()
            if now - sess.get("_last_access", 0) > SESSION_TIMEOUT
        ]
        for uid in expired:
            del chat_sessions[uid]
        if expired:
            print(f"🧹 清除 {len(expired)} 個過期對話")


# ========== 使用者自訂提示詞 ==========
user_prompts = {}
user_prompts_lock = Lock()


def get_system_prompt(user_id: str) -> str:
    """取得使用者的系統提示詞（自訂或預設）"""
    with user_prompts_lock:
        return user_prompts.get(user_id, DEFAULT_SYSTEM_PROMPT)


def set_user_prompt(user_id: str, prompt: str):
    """設定使用者的自訂提示詞"""
    with user_prompts_lock:
        user_prompts[user_id] = prompt
    # 若使用者有進行中的對話，同步更新 system prompt
    with chat_sessions_lock:
        if user_id in chat_sessions:
            chat_sessions[user_id]["messages"][0]["content"] = prompt


def reset_user_prompt(user_id: str):
    """恢復使用者的預設提示詞"""
    with user_prompts_lock:
        if user_id in user_prompts:
            del user_prompts[user_id]


def has_custom_prompt(user_id: str) -> bool:
    """檢查使用者是否有自訂提示詞"""
    with user_prompts_lock:
        return user_id in user_prompts
