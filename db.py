"""資料庫持久層：本地 SQLite / Turso 雲端（HTTP API）"""

import os
import time
from threading import Lock

import libsql_client as lc
import requests

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "bot.db")

TURSO_URL = os.getenv("TURSO_DB_URL")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

db_lock = Lock()
_use_local = not (TURSO_URL and TURSO_TOKEN)


# ========== Turso HTTP 客戶端 ==========

class _TursoDB:
    """透過 Turso HTTP REST API 操作資料庫"""

    def __init__(self, base_url: str, token: str):
        self.endpoint = base_url.replace("libsql://", "https://") + "/v2/pipeline"
        self.token = token

    def _request(self, sql: str, params=None):
        body = {"requests": [{"type": "execute", "stmt": {"sql": sql, "args": params or []}}]}
        r = requests.post(self.endpoint, headers={"Authorization": f"Bearer {self.token}"}, json=body, timeout=15)
        r.raise_for_status()
        results = r.json()["results"]
        if results and "result" in results[0]:
            cols = results[0]["result"]["cols"]
            rows = results[0]["result"]["rows"]
            return [dict(zip(cols, row)) for row in rows]
        return []

    def execute(self, sql, params=None):
        return self._request(sql, params)

    def execute_dml(self, sql, params=None):
        self._request(sql, params)

    def batch(self, statements):
        payload = [{"type": "execute", "stmt": {"sql": s["sql"], "args": s.get("args", [])}} for s in statements]
        r = requests.post(self.endpoint, headers={"Authorization": f"Bearer {self.token}"}, json={"requests": payload}, timeout=15)
        r.raise_for_status()

    def close(self):
        pass


# ========== 本地 SQLite 客戶端 ==========

class _LocalDB:
    """本地 SQLite（libsql_client file: 協定）"""

    def __init__(self):
        os.makedirs(DB_DIR, exist_ok=True)
        self.client = lc.create_client_sync(url=f"file:{DB_PATH}")

    def execute(self, sql, params=None):
        result = self.client.execute(sql, params or [])
        if result.columns:
            return [dict(zip(result.columns, row)) for row in result.rows]
        return []

    def execute_dml(self, sql, params=None):
        self.client.execute(sql, params or [])

    def batch(self, statements):
        stmts = [lc.Statement(s["sql"], s.get("args", [])) for s in statements]
        self.client.batch(stmts)

    def close(self):
        self.client.close()


# ========== 客戶端工廠 ==========

def _get_db():
    global _use_local
    if not _use_local:
        try:
            db = _TursoDB(TURSO_URL, TURSO_TOKEN)
            db.execute("SELECT 1")
            return db
        except Exception as e:
            print(f"⚠️  Turso 連線失敗：{e}")
            print("💡 自動切換為本地 SQLite")
            _use_local = True
    return _LocalDB()


def init_db():
    with db_lock:
        db = _get_db()
        try:
            db.batch([
                {"sql": "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL)"},
                {"sql": "CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id)"},
                {"sql": "CREATE TABLE IF NOT EXISTS user_prompts (user_id TEXT PRIMARY KEY, prompt TEXT NOT NULL, updated_at REAL NOT NULL)"},
            ])
        finally:
            db.close()
    mode = "☁️ Turso 雲端" if not _use_local else "💾 本地 SQLite"
    print(f"🗄️  資料庫初始化完成（{mode}）")


# ========== 訊息操作 ==========

def save_message(user_id, role, content):
    with db_lock:
        db = _get_db()
        db.execute_dml("INSERT INTO messages (user_id, role, content, created_at) VALUES (?, ?, ?, ?)", [user_id, role, content, time.time()])
        db.close()


def load_messages(user_id, limit=21):
    with db_lock:
        db = _get_db()
        rows = db.execute("SELECT role, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?", [user_id, limit])
        db.close()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def delete_user_messages(user_id):
    with db_lock:
        db = _get_db()
        db.execute_dml("DELETE FROM messages WHERE user_id = ?", [user_id])
        db.close()


def cleanup_expired_messages(timeout):
    cutoff = time.time() - timeout
    with db_lock:
        db = _get_db()
        rows = db.execute("SELECT COUNT(*) as cnt FROM messages WHERE created_at < ?", [cutoff])
        count = rows[0]["cnt"] if rows else 0
        if count:
            db.execute_dml("DELETE FROM messages WHERE created_at < ?", [cutoff])
        db.close()
    if count:
        print(f"🧹 清除 {count} 則過期訊息")


# ========== 提示詞操作 ==========

def save_user_prompt(user_id, prompt):
    with db_lock:
        db = _get_db()
        db.execute_dml("INSERT OR REPLACE INTO user_prompts (user_id, prompt, updated_at) VALUES (?, ?, ?)", [user_id, prompt, time.time()])
        db.close()


def load_user_prompt(user_id):
    with db_lock:
        db = _get_db()
        rows = db.execute("SELECT prompt FROM user_prompts WHERE user_id = ?", [user_id])
        db.close()
    return rows[0]["prompt"] if rows else None


def delete_user_prompt(user_id):
    with db_lock:
        db = _get_db()
        db.execute_dml("DELETE FROM user_prompts WHERE user_id = ?", [user_id])
        db.close()


def load_all_prompts():
    with db_lock:
        db = _get_db()
        rows = db.execute("SELECT user_id, prompt FROM user_prompts")
        db.close()
    return {r["user_id"]: r["prompt"] for r in rows}
