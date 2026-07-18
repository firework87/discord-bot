# Discord AI Bot

使用 OpenRouter API 的 Discord AI 聊天機器人，支援多個免費 AI 模型自動切換。

## 專案結構

```
discord-bot/
├── bot.py                # 主入口：Discord 指令、事件、啟動
├── config.py             # 設定：API 金鑰、模型列表、共用常數
├── web_server.py         # Flask 伺服器（供 Render 等平台健康檢查）
├── ai_client.py          # AI 呼叫邏輯：OpenRouter API 互動
├── session_manager.py    # 對話 session 與自訂提示詞管理
├── requirements.txt
└── README.md
```

## 環境設定

建立 `.env` 檔案並填入：

```
DISCORD_TOKEN=你的Discord機器人Token
OPENROUTER_KEY_API_KEY=你的OpenRouter API Key
```

## 安裝與執行

```bash
pip install -r requirements.txt
python bot.py
```

## 指令
- `!ask <問題>` — 單次問答（無對話記憶）
- `!chat <訊息>` — 有記憶的連續對話（1 小時過期）
- `!prompt <角色>` — 自訂 AI 角色，例如 `!prompt 你是貓咪，都要加喵~`
- `!prompt` — 查看目前提示詞
- `!prompt reset` — 恢復預設提示詞
- `!reset` — 清除你的對話記憶
- `!helpme` — 顯示幫助訊息
- `!models` — 查看目前可用的 AI 模型
- `@機器人 <訊息>` — 直接提及機器人也會回覆
