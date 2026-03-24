import discord
from discord.ext import commands
import os
from threading import Thread
from flask import Flask

# 1. 環境変数の取得（RenderのEnvironment設定と名前を完全に一致させてください）
TOKEN = os.getenv('DISCORD_TOKEN')

app = Flask('')
@app.route('/')
def home(): return "Flask is Running!"

def run_flask():
    # Renderのポート10000番で待機
    app.run(host='0.0.0.0', port=10000)

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)

    async def on_ready(self):
        print(f"✅ ✅ ✅ ログイン成功: {self.user.name} ✅ ✅ ✅")

bot = MyBot()

@bot.command()
async def test(ctx):
    await ctx.send("疎通確認成功！ボットは生きています！")

if __name__ == "__main__":
    # Flaskを別スレッドで起動（UptimeRobot対策）
    Thread(target=run_flask).start()
    
    print("🚀 Discordへのログインを試行中...")
    if not TOKEN:
        print("❌ エラー: DISCORD_TOKEN が空です。RenderのEnvironment設定を確認してください。")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            print(f"❌ ログインエラー発生: {e}")
