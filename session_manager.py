"""對話 Session 與提示詞管理（SQLite 持久化）"""

import time
from threading import Lock
from config import DEFAULT_SYSTEM_PROMPT, SESSION_TIMEOUT
import db

# ========== 初始化 ==========
db.init_db()

# 從 DB 載入所有自訂提示詞到記憶體快取
user_prompts = db.load_all_prompts()
user_prompts_lock = Lock()

# ========== 對話 Session（記憶體快取）==========
chat_sessions = {}
chat_sessions_lock = Lock()


def cleanup_old_sessions():
    """清除過期的對話 session（記憶體 + DB）"""
    now = time.time()
    with chat_sessions_lock:
        expired = [
            uid for uid, sess in chat_sessions.items()
            if now - sess.get("_last_access", 0) > SESSION_TIMEOUT
        ]
        for uid in expired:
            del chat_sessions[uid]
    if expired:
        print(f"🧹 清除 {len(expired)} 個過期對話（記憶體）")

    # 也清除 DB 中的過期記錄
    db.cleanup_expired_messages(SESSION_TIMEOUT)


def restore_session(user_id: str) -> list[dict] | None:
    """嘗試從 DB 恢復使用者的對話 session，成功則載入記憶體"""
    messages = db.load_messages(user_id)
    if messages:
        with chat_sessions_lock:
            chat_sessions[user_id] = {
                "messages": messages,
                "_last_access": time.time()
            }
        return messages
    return None


def save_message(user_id: str, role: str, content: str):
    """儲存一則訊息到 DB"""
    db.save_message(user_id, role, content)


def delete_session(user_id: str):
    """刪除使用者的對話（記憶體 + DB）"""
    with chat_sessions_lock:
        if user_id in chat_sessions:
            del chat_sessions[user_id]
    db.delete_user_messages(user_id)


# ========== 使用者自訂提示詞（記憶體快取 + DB 持久化）==========


def get_system_prompt(user_id: str) -> str:
    """取得使用者的系統提示詞（自訂或預設）"""
    with user_prompts_lock:
        return user_prompts.get(user_id, DEFAULT_SYSTEM_PROMPT)


def set_user_prompt(user_id: str, prompt: str):
    """設定使用者的自訂提示詞（記憶體 + DB）"""
    with user_prompts_lock:
        user_prompts[user_id] = prompt
    db.save_user_prompt(user_id, prompt)

    # 若使用者有進行中的對話，同步更新 system prompt
    with chat_sessions_lock:
        if user_id in chat_sessions:
            chat_sessions[user_id]["messages"][0]["content"] = prompt


def reset_user_prompt(user_id: str):
    """恢復使用者的預設提示詞（記憶體 + DB）"""
    with user_prompts_lock:
        if user_id in user_prompts:
            del user_prompts[user_id]
    db.delete_user_prompt(user_id)


def has_custom_prompt(user_id: str) -> bool:
    """檢查使用者是否有自訂提示詞"""
    with user_prompts_lock:
        return user_id in user_prompts
