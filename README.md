# Discord AI Bot

使用 DeepSeek API 為主的 AI 聊天機器人，**DeepSeek 優先、OpenRouter 備用**，內建 SQLite 持久化。

## 專案結構

```
discord-bot/
├── bot.py                # 主入口：Discord 指令、事件、啟動
├── config.py             # 設定：API 金鑰、模型列表、雙客戶端
├── web_server.py         # Flask 伺服器（供 Render 等平台健康檢查）
├── ai_client.py          # AI 呼叫邏輯：DeepSeek → OpenRouter 自動切換
├── session_manager.py    # 對話 session 與提示詞管理（記憶體 + DB）
├── db.py                 # SQLite 持久層（對話記錄、自訂提示詞）
├── data/                 # 執行時產生：bot.db 資料庫
├── requirements.txt
└── README.md
```

## 環境設定

在專案根目錄建立 `.env` 檔案，逐項填入以下內容：

```env
# ========== 必填 ==========

# Discord Bot Token
# 取得方式：https://discord.com/developers/applications → 你的 App → Bot → Reset Token
DISCORD_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNA.xxxxx.xxxxxxxxxxxxxxxxxxxx

# OpenRouter API Key（備用 AI，免費）
# 取得方式：https://openrouter.ai/keys → Create Key
OPENROUTER_KEY_API_KEY=sk-or-v1-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


# ========== 選填：主要 AI（建議設定）==========

# DeepSeek API Key
# 取得方式：https://platform.deepseek.com/api_keys → 建立 API Key
# 若未設定，會自動改用 OpenRouter 免費模型
DEEPSEEK_API=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx


# ========== 選填：跨部署永久記憶 ==========

# Turso 資料庫 URL（格式：libsql://資料庫名稱-組織名稱.turso.io）
# 取得方式：終端機執行 turso db create discord-bot 後會顯示
TURSO_DB_URL=libsql://discord-bot-your-org.turso.io

# Turso 驗證 Token
# 取得方式：終端機執行 turso db tokens create discord-bot
TURSO_AUTH_TOKEN=eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 各參數說明

| 參數 | 必填 | 說明 | 去哪裡拿 |
|------|:--:|------|----------|
| `DISCORD_TOKEN` | ✅ | Discord 機器人 Token | [Discord Developer Portal](https://discord.com/developers/applications) → Bot |
| `OPENROUTER_KEY_API_KEY` | ✅ | OpenRouter API 免費金鑰 | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `DEEPSEEK_API` | ❌ | DeepSeek API 金鑰，沒填就只用 OpenRouter | [platform.deepseek.com](https://platform.deepseek.com/api_keys) |
| `TURSO_DB_URL` | ❌ | Turso 雲端資料庫位址，沒填就用本地檔案 | `turso db create` 指令輸出 |
| `TURSO_AUTH_TOKEN` | ❌ | Turso 驗證 Token | `turso db tokens create` 指令輸出 |

## 安裝與執行

```bash
pip install -r requirements.txt
python bot.py
```

## 指令
- `!ask <問題>` — 單次問答（無對話記憶）
- `!chat <訊息>` — 有記憶的連續對話（1 小時過期，跨重啟保留）
- `!prompt <角色>` — 自訂 AI 角色，例如 `!prompt 你是貓咪，都要加喵~`
- `!prompt` — 查看目前提示詞
- `!prompt reset` — 恢復預設提示詞
- `!reset` — 清除你的對話記憶
- `!helpme` — 顯示幫助訊息
- `!models` — 查看目前可用的 AI 模型
- `@機器人 <訊息>` — 直接提及機器人也會回覆
