"""資料庫持久層：本地 SQLite / Turso 雲端自動切換"""

import os
import time
from threading import Lock

import libsql_client as lc

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "bot.db")

TURSO_URL = os.getenv("TURSO_DB_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

db_lock = Lock()


def _get_client() -> lc.ClientSync:
    """取得資料庫客戶端（本地 SQLite 或 Turso 雲端）"""
    if TURSO_URL and TURSO_TOKEN:
        client = lc.create_client_sync(url=TURSO_URL, auth_token=TURSO_TOKEN)
    else:
        os.makedirs(DB_DIR, exist_ok=True)
        client = lc.create_client_sync(url=f"file:{DB_PATH}")
    return client


def init_db():
    """初始化資料庫表格"""
    with db_lock:
        client = _get_client()
        client.batch([
            lc.Statement("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """),
            lc.Statement("""
                CREATE INDEX IF NOT EXISTS idx_messages_user 
                    ON messages(user_id, id)
            """),
            lc.Statement("""
                CREATE TABLE IF NOT EXISTS user_prompts (
                    user_id TEXT PRIMARY KEY,
                    prompt TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """),
        ])
        client.close()

    mode = "☁️ Turso 雲端" if TURSO_URL else "💾 本地 SQLite"
    print(f"🗄️  資料庫初始化完成（{mode}）")


# ========== 訊息操作 ==========

def save_message(user_id: str, role: str, content: str):
    """儲存一則對話訊息"""
    with db_lock:
        client = _get_client()
        client.execute(
            "INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            [user_id, role, content, time.time()]
        )
        client.close()


def load_messages(user_id: str, limit: int = 21) -> list[dict]:
    """載入使用者的對話記錄（最近 N 則）"""
    with db_lock:
        client = _get_client()
        result = client.execute(
            "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            [user_id, limit]
        )
        client.close()
    return [{"role": r, "content": c} for r, c in reversed(result.rows)]


def delete_user_messages(user_id: str):
    """刪除使用者的所有對話記錄"""
    with db_lock:
        client = _get_client()
        client.execute("DELETE FROM messages WHERE user_id = ?", [user_id])
        client.close()


def cleanup_expired_messages(timeout: float):
    """清除過期的對話記錄"""
    cutoff = time.time() - timeout
    with db_lock:
        client = _get_client()
        result = client.execute(
            "SELECT COUNT(*) FROM messages WHERE created_at < ?", [cutoff]
        )
        count = result.rows[0][0] if result.rows else 0
        if count:
            client.execute("DELETE FROM messages WHERE created_at < ?", [cutoff])
        client.close()
    if count:
        print(f"🧹 清除 {count} 則過期訊息")


# ========== 提示詞操作 ==========

def save_user_prompt(user_id: str, prompt: str):
    """儲存使用者自訂提示詞"""
    with db_lock:
        client = _get_client()
        client.execute(
            "INSERT OR REPLACE INTO user_prompts (user_id, prompt, updated_at) VALUES (?, ?, ?)",
            [user_id, prompt, time.time()]
        )
        client.close()


def load_user_prompt(user_id: str) -> str | None:
    """載入使用者的自訂提示詞"""
    with db_lock:
        client = _get_client()
        result = client.execute(
            "SELECT prompt FROM user_prompts WHERE user_id = ?", [user_id]
        )
        client.close()
    return result.rows[0][0] if result.rows else None


def delete_user_prompt(user_id: str):
    """刪除使用者的自訂提示詞"""
    with db_lock:
        client = _get_client()
        client.execute("DELETE FROM user_prompts WHERE user_id = ?", [user_id])
        client.close()


def load_all_prompts() -> dict[str, str]:
    """載入所有使用者的自訂提示詞"""
    with db_lock:
        client = _get_client()
        result = client.execute("SELECT user_id, prompt FROM user_prompts")
        client.close()
    return {uid: prompt for uid, prompt in result.rows}
