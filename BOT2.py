import discord
from discord.ext import commands, tasks
import datetime
import requests
import os
import feedparser
from flask import Flask
from threading import Thread

# ================= config =================
# 1. 通知を送るチャンネルID（ここを自分のサーバーのものに書き換えてください！）
ANNOUNCE_CH_ID = 1476095569595334718

# 2. Twitter（Nitter）の設定
# 取得したいTwitterIDの後に /rss をつけたもの
RSS_URL = "https://nitter.net/ucg_jp/rss" 
# 検索したいキーワード
KEYWORDS = ["新カード", "公開", "速報", "メンテナンス"]

# 3. 環境変数から取得（Renderで設定したもの）
TOKEN = os.getenv("DISCORD_TOKEN")
GAS_URL = os.getenv("GAS_URL")
# ==========================================

# Flaskサーバーの設定（Renderの居眠り防止用）
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

# Discord Botの設定
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 前回の最新記事URLを保存する変数
last_entry_url = None

@bot.event
async def on_ready():
    print(f"--- {bot.user} としてログインしました ---")
    # 15分タイマーを開始
    if not check_twitter.is_running():
        check_twitter.start()
        print("Twitter監視タイマーを開始しました（15分おき）")

@tasks.loop(minutes=15)
async def check_twitter():
    global last_entry_url
    print(f"[{datetime.datetime.now()}] Twitterチェック中...")
    
    try:
        # NitterからRSSを取得
        feed = feedparser.parse(RSS_URL)
        if not feed.entries:
            print("投稿が見つかりませんでした（Nitter側のエラーの可能性があります）")
            return

        latest = feed.entries[0]
        
        # すでに通知済みの記事なら何もしない
        if latest.link == last_entry_url:
            print("新しい投稿はありませんでした。")
            return

        # キーワードチェック
        if any(k in latest.title for k in KEYWORDS):
            channel = bot.get_channel(ANNOUNCE_CH_ID)
            if channel:
                await channel.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
                print(f"通知を送信しました: {latest.title}")
            else:
                print(f"エラー: チャンネルID {ANNOUNCE_CH_ID} が見つかりません。")
        
        # 最新のURLを保存
        last_entry_url = latest.link

    except Exception as e:
        print(f"Twitterチェック中にエラーが発生しました: {e}")

# --- ボイスチャンネル（VC）の処理 ---
user_start_times = {}

@bot.event
async def on_voice_state_update(member, before, after):
    # 誰かがVCに入ったとき
    if before.channel is None and after.channel is not None:
        user_start_times[member.id] = datetime.datetime.now()
        
        # 2人目が入ったときにダイス（先攻・後攻）を振る
        if len(after.channel.members) == 2:
            import random
            p1, p2 = after.channel.members
            first = random.choice([p1, p2])
            second = p2 if first == p1 else p1
            await after.channel.send(f"🎲 対戦開始！\n【先攻】{first.mention}\n【後攻】{second.mention}")

    # 誰かがVCから出たとき
    elif before.channel is not None and after.channel is None:
        if member.id in user_start_times:
            end_time = datetime.datetime.now()
            duration = end_time - user_start_times[member.id]
            duration_min = int(duration.total_seconds() / 60)

            # GAS（スプレッドシート）へデータを送信
            if GAS_URL:
                data = {
                    "user": member.name,
                    "duration": duration_min,
                    "date": end_time.strftime("%Y-%m-%d %H:%M:%S")
                }
                try:
                    requests.post(GAS_URL, json=data)
                    print(f"記録を送信: {member.name} / {duration_min}分")
                except Exception as e:
                    print(f"GAS送信エラー: {e}")
            
            del user_start_times[member.id]

# Flaskを別スレッドで起動
Thread(target=run_flask).start()

# Botを起動
bot.run(TOKEN)
