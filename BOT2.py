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
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')

ROLE_ID = 1478266543480766716
ANNOUNCE_CH_ID = 1476095569595334718 # ログとTwitter速報用
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='TCG IDを入力', placeholder='例: 12345678', min_length=1)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
        requests.post(GAS_URL, json=payload, timeout=5)
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

class MainViews(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 参加承認", style=discord.ButtonStyle.green, custom_id="c_v11")
    async def agree(self, it, b):
        role = it.guild.get_role(ROLE_ID)
        await it.user.add_roles(role)
        await it.response.send_message("承認されました！", ephemeral=True)
    @discord.ui.button(label="📝 ID登録", style=discord.ButtonStyle.primary, custom_id="r_v11")
    async def reg(self, it, b): await it.response.send_modal(RegistrationModal())

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.guilds = intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        self.match_starts = {}
        self.last_link = None

    async def on_ready(self):
        self.add_view(MainViews())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'Logged in as {self.user.name}')

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            # GAS経由でTwitter取得（Renderブロック回避）
            response = requests.get(GAS_URL, params={'type': 'fetch_rss'}, timeout=20)
            feed = feedparser.parse(response.text)
            if not feed.entries: return
            latest = feed.entries[0]
            if self.last_link == latest.link: return
            
            keywords = ['カードデザイン', '公開', '新カード']
            if any(k in latest.title for k in keywords):
                ch = self.get_channel(ANNOUNCE_CH_ID)
                if ch: await ch.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
            self.last_link = latest.link
        except: pass

    async def on_voice_state_update(self, member, before, after):
        # 対戦開始
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            self.match_starts[after.channel.id] = {
                "time": datetime.datetime.now(), 
                "p1_name": p1.name, "p2_name": p2.name,
                "p1_id": p1.id, "p2_id": p2.id
            }
            await after.channel.send(f"🎲 **対戦開始**: {p1.mention} vs {p2.mention}", silent=True)

        # 対戦終了
        elif
