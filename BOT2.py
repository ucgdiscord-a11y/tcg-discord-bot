import discord
from discord.ext import commands, tasks
import random
import datetime
import requests
import os
import feedparser
from threading import Thread
from flask import Flask

# ================= 設定項目（環境変数から読み込み） =================
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')
ROLE_ID = 1478266543480766716        # 同意時に付与する役職ID
ANNOUNCE_CH_ID = 1476095569595334718 # Twitter通知用
WELCOME_CH_ID = 1464168951012393021  # 挨拶用
RSS_URL = 'https://nitter.perennialte.ch/ucg_jp/rss'
KEYWORDS = ['カードデザイン', '公開', '新カード']
# ==============================================================

# Render居眠り防止用
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- 1. TCG ID登録（3秒の壁 対策済み） ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678', min_length=1, required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        # タイムアウト回避（まず「考え中...」にする）
        await interaction.response.defer(ephemeral=True)
        
        if GAS_URL:
            payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
            try: requests.post(GAS_URL, json=payload, timeout=10)
            except Exception as e: print(f"GAS送信エラー: {e}")
            
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="reg_modal_btn_v3")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal())

# --- 2. サーバー参加・承認 ---
class ConsentView(discord.ui.View):
    def __init__(self): super().__init__(timeout
