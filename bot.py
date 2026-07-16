import discord
from discord.ext import commands
from openai import OpenAI
import requests
import os

# ========== 設定區 ==========
from dotenv import load_dotenv
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_KEY_API_KEY")


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

# ========== 自動抓取可用免費模型 ==========
def get_free_models():
    """從 OpenRouter API 抓取目前可用的免費模型"""
    try:
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"}
        )
        data = resp.json()
        
        free_models = []
        for m in data.get("data", []):
            model_id = m.get("id", "")
            # 找免費模型（價格為 0 或名稱含 free）
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
FREE_MODELS = get_free_models()

# 如果抓不到，用預設備用
if not FREE_MODELS:
    FREE_MODELS = [
        "meta-llama/llama-3.2-3b-instruct:free",
        "mistralai/mistral-7b-instruct:free", 
        "huggingfaceh4/zephyr-7b-beta:free",
    ]
    print("⚠️ 使用預設備用模型")

CURRENT_MODEL = FREE_MODELS[0] if FREE_MODELS else None

# ========== Discord 設定 ==========
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

chat_sessions = {}

@bot.event
async def on_ready():
    print(f"✅ 機器人已上線：{bot.user}")
    if CURRENT_MODEL:
        print(f"使用模型：{CURRENT_MODEL}")
    else:
        print("❌ 沒有可用的免費模型！")

def ask_ai(question, model_index=0):
    """呼叫 AI，自動切換模型"""
    if not FREE_MODELS or model_index >= len(FREE_MODELS):
        return "❌ 目前沒有可用的免費模型，請稍後再試或查看 https://openrouter.ai/models"
    
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
        
        # 自動切換下一個
        if any(x in error_msg for x in ["404", "400", "rate limit", "quota", "not a valid"]):
            return ask_ai(question, model_index + 1)
        raise e

@bot.command()
async def ask(ctx, *, question):
    async with ctx.typing():
        try:
            answer = ask_ai(question)
            
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
            
            # 嘗試每個模型
            answer = None
            for model in FREE_MODELS:
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=chat_sessions[user_id],
                        max_tokens=1000,
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

@bot.command()
async def models(ctx):
    """查看目前可用的免費模型"""
    model_list = "\n".join([f"• `{m}`" for m in FREE_MODELS[:10]])
    await ctx.reply(f"📋 目前可用的免費模型（前10個）：\n{model_list}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if bot.user.mentioned_in(message):
        clean_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if clean_text:
            async with message.channel.typing():
                try:
                    answer = ask_ai(clean_text)
                    await message.reply(f"🤖 {answer}")
                except Exception as e:
                    await message.reply(f"❌ 錯誤：{str(e)[:300]}")
    
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
