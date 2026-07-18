"""bot.py — Discord AI Bot 主入口：指令、事件、啟動"""

import time
import discord
from discord.ext import commands

from config import DISCORD_TOKEN, FREE_MODELS, CURRENT_MODEL
from web_server import start_web_server
from ai_client import ask_ai, safe_typing, send_long_message
from session_manager import (
    chat_sessions, chat_sessions_lock,
    cleanup_old_sessions,
    get_system_prompt,
    set_user_prompt, reset_user_prompt,
    has_custom_prompt,
)

# ========== Discord Bot 初始化 ==========
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ========== 事件 ==========

@bot.event
async def on_ready():
    print(f"✅ 機器人已上線：{bot.user}")
    print(f"使用模型：{CURRENT_MODEL}")


@bot.event
async def on_message(message):
    """處理 @提及 訊息"""
    if message.author == bot.user:
        return

    if bot.user.mentioned_in(message):
        clean_text = message.content.replace(f"<@{bot.user.id}>", "").strip()
        if clean_text:
            await safe_typing(message.channel)
            try:
                user_id = str(message.author.id)
                messages = [
                    {"role": "system", "content": get_system_prompt(user_id)},
                    {"role": "user", "content": clean_text}
                ]
                answer = await ask_ai(messages)
                await message.reply(f"🤖 {answer}")
            except Exception as e:
                await message.reply(f"❌ 錯誤：{str(e)[:300]}")

    await bot.process_commands(message)


# ========== 指令 ==========

@bot.command()
async def ask(ctx, *, question):
    """單次問答（無記憶）"""
    await safe_typing(ctx)
    try:
        user_id = str(ctx.author.id)
        messages = [
            {"role": "system", "content": get_system_prompt(user_id)},
            {"role": "user", "content": question}
        ]
        answer = await ask_ai(messages)

        if len(answer) > 1900:
            await send_long_message(ctx, answer)
        else:
            await ctx.reply(f"🤖 {answer}")
    except Exception as e:
        await ctx.reply(f"❌ 出錯：{str(e)[:500]}")


@bot.command()
async def chat(ctx, *, message):
    """有記憶的對話"""
    user_id = str(ctx.author.id)

    await safe_typing(ctx)
    try:
        with chat_sessions_lock:
            cleanup_old_sessions()

            if user_id not in chat_sessions:
                chat_sessions[user_id] = {
                    "messages": [
                        {"role": "system", "content": get_system_prompt(user_id)}
                    ],
                    "_last_access": time.time()
                }

            session = chat_sessions[user_id]
            session["_last_access"] = time.time()

            # 若使用者更換了提示詞，同步更新 system prompt
            current_prompt = get_system_prompt(user_id)
            if session["messages"][0]["content"] != current_prompt:
                session["messages"][0]["content"] = current_prompt

            session["messages"].append({"role": "user", "content": message})

            # 保留 system prompt + 最近 10 則對話（20 則訊息）
            if len(session["messages"]) > 21:
                session["messages"] = [session["messages"][0]] + session["messages"][-20:]

            messages = session["messages"]

        answer = await ask_ai(messages)

        with chat_sessions_lock:
            if user_id in chat_sessions:
                chat_sessions[user_id]["messages"].append(
                    {"role": "assistant", "content": answer}
                )
                chat_sessions[user_id]["_last_access"] = time.time()

        if len(answer) > 1900:
            await send_long_message(ctx, answer)
        else:
            await ctx.reply(f"🤖 {answer}")

    except Exception as e:
        await ctx.reply(f"❌ 出錯：{str(e)[:500]}")


@bot.command()
async def reset(ctx):
    """清除對話記憶"""
    user_id = str(ctx.author.id)
    with chat_sessions_lock:
        if user_id in chat_sessions:
            del chat_sessions[user_id]
            await ctx.reply("🗑️ 對話記憶已清除！")
        else:
            await ctx.reply("ℹ️ 沒有對話記憶需要清除")


@bot.command()
async def prompt(ctx, *, action=""):
    """自訂 AI 角色提示詞

    用法：
    !prompt              → 查看你目前的提示詞
    !prompt <內容>       → 設定新的提示詞
    !prompt reset        → 恢復預設提示詞
    """
    user_id = str(ctx.author.id)
    action = action.strip()

    if not action:
        current = get_system_prompt(user_id)
        status = "✏️ 自訂" if has_custom_prompt(user_id) else "📋 預設"
        await ctx.reply(f"{status}提示詞：\n```\n{current}\n```")
        return

    if action.lower() == "reset":
        reset_user_prompt(user_id)
        await ctx.reply("🔄 已恢復為預設提示詞！")
        return

    if len(action) > 500:
        await ctx.reply("⚠️ 提示詞太長了，請限制在 500 字以內。")
        return

    set_user_prompt(user_id, action)
    await ctx.reply(f"✅ 已設定你的 AI 角色：\n```\n{action}\n```")


@bot.command()
async def helpme(ctx):
    """顯示幫助訊息"""
    help_text = (
        "**🤖 Discord AI Bot 指令列表**\n\n"
        "`!ask <問題>` — 單次問答（沒有對話記憶）\n"
        "`!chat <訊息>` — 有記憶的連續對話\n"
        "`!prompt <角色>` — 自訂 AI 角色（`!prompt reset` 恢復預設）\n"
        "`!reset` — 清除你的對話記憶\n"
        "`!helpme` — 顯示此幫助訊息\n"
        "`!models` — 查看當前使用的 AI 模型\n"
        f"\n🎯 當前模型：`{CURRENT_MODEL}`"
    )
    await ctx.reply(help_text)


@bot.command()
async def models(ctx):
    """查看可用模型"""
    model_list = "\n".join(f"• `{m}`" for m in FREE_MODELS[:10])
    await ctx.reply(
        f"🎯 **當前模型：** `{CURRENT_MODEL}`\n\n"
        f"**可用免費模型：**\n{model_list}"
    )


# ========== 啟動 ==========
if __name__ == "__main__":
    start_web_server()
    bot.run(DISCORD_TOKEN)
