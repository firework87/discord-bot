"""Web 伺服器：讓 Render 等平台知道服務活著"""

import os
from threading import Thread
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot is running!"

def start_web_server():
    """啟動 Flask 伺服器（在背景執行緒）"""
    port = int(os.environ.get("PORT", 8080))
    Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
