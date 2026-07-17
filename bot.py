from flask import Flask
from threading import Thread
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

# ========== Web 伺服器（讓 Render 知道服務活著）==========
app = Flask('')

@app.route('/')
def home():
    return "🤖 Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

Thread(target=run_web).start()

# ========== Discord Bot ==========
import discord
from discord.ext import commands
from openai import OpenAI

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY_API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

FREE_MODELS = [
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "google/gemini-2.0-pro-exp-02-05:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "deepseek/deepseek-chat:free",
]

CURRENT_MODEL = FREE_MODELS[0]

# 執行緒池
executor = ThreadPoolExecutor(max_workers=2)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

chat_sessions = {}

@bot.event
async def on_ready():
    print(f"✅ 機器人已上線：{bot.user}")
    print(f"使用模型：{CURRENT_MODEL}")

def _ask_ai_sync(question, model_index=0):
    """同步版本（在背景執行緒跑）"""
    if model_index >= len(FREE_MODELS):
        return "❌ 所有免費模型都暫時無法使用，請稍後再試。"
    
    model = FREE_MODELS[model_index]
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一個有幫助的助手，用繁體中文回答。"},
                {"role": "user", "content": question}
            ],
            max_tokens=1000,
        )
        return response.choices[0].message.content
        
    except Exception as e:
        error_msg = str(e)
        print(f"⚠️ {model} 失敗：{error_msg[:100]}")
        
        if any(x in error_msg for x in ["404", "400", "rate limit", "quota", "not a valid"]):
            return _ask_ai_sync(question, model_index + 1)
        raise e

async def ask_ai(question, model_index=0):
    """非同步版本（不阻塞 Discord）"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _ask_ai_sync, question, model_index)

@bot.command()
async def ask(ctx, *, question):
    async with ctx.typing():
        try:
            answer = await ask_ai(question)
            
            if len(answer) > 1900:
                for i in range(0, len(answer), 1900):
                    await ctx.send(answer[i:i+1900])
            else:
                await ctx.reply(f"🤖 {answer}")
        except Exception as e:
            await ctx.reply(f"❌ 出錯：{str(e)[:500]}")

@bot.command()
async def chat(ctx, *, message):
    user_id = str(ctx.author.id)
    
    async with ctx.typing():
        try:
            if user_id not in chat_sessions:
                chat_sessions[user_id] = [
                    {"role": "system", "content": "你是一個有幫助的助手，用繁體中文回答。"}
                ]
            
            chat_sessions[user_id].append({"role": "user", "content": message})
            
            if len(chat_sessions[user_id]) > 12:
                chat_sessions[user_id] = [chat_sessions[user_id][0]] + chat_sessions[user_id][-10:]
            
            answer = None
            for model in FREE_MODELS:
                try:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        executor,
                        lambda: client.chat.completions.create(
                            model=model,
                            messages=chat_sessions[user_id],
                            max_tokens=1000,
                        )
                    )
                    answer = response.choices[0].message.content
                    break
                except Exception as e:
                    print(f"⚠️ {model} 失敗")
                    continue
            
            if not answer:
                answer = "❌ 所有模型都暫時無法使用"
            
            chat_sessions[user_id].append({"role": "assistant", "content": answer})
            
            if len(answer) > 1900:
                for i in range(0, len(answer), 1900):
                    await ctx.send(answer[i:i+1900])
            else:
                await ctx.reply(f"🤖 {answer}")
                
        except Exception as e:
            await ctx.reply(f"❌ 出錯：{str(e)[:500]}")

@bot.command()
async def reset(ctx):
    user_id = str(ctx.author.id)
    if user_id in chat_sessions:
        del chat_sessions[user_id]
        await ctx.reply("🗑️ 對話記憶已清除！")
    else:
        await ctx.reply("ℹ️ 沒有對話記憶需要清除")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message):
        clean_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if clean_text:
            async with message.channel.typing():
                try:
                    answer = await ask_ai(clean_text)
                    await message.reply(f"🤖 {answer}")
                except Exception as e:
                    await message.reply(f"❌ 錯誤：{str(e)[:300]}")
    
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
