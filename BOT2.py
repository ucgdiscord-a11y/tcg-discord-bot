import discord
from discord.ext import commands, tasks
import random
import feedparser
import requests
import datetime
import os
from threading import Thread
from flask import Flask

# ================= 設定項目 =================
# Renderの Environment Variables に登録してください
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')

ROLE_ID = 1478266543480766716        # 承認用
ANNOUNCE_CH_ID = 1476095569595334718 # Twitter速報用
WELCOME_CH_ID = 1464168951012393021  # 挨拶用

# クラウドからでもブロックされにくいURLに設定
RSS_URL = 'https://nitter.poast.org/ucg_jp/rss'
KEYWORDS = ['カードデザイン', '公開', '新カード']
# ===========================================

# Renderの居眠り防止用
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- 1. TCG ID登録モーダル（3秒エラー回避版） ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG IDを入力してください', placeholder='例: 12345678', min_length=1, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # 通信中の「考え中」状態を作る
        payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
        try:
            requests.post(GAS_URL, json=payload, timeout=10)
        except: pass
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

# --- 2. 各種ビュー（画像デザイン完全再現） ---
class ConsentView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="c_btn")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("承認されました！", ephemeral=True)
        except: await interaction.response.send_message("エラー：権限不足です。ボットの役職を上げてください。", ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="reg_btn")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send
