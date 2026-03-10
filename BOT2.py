import discord
from discord.ext import commands, tasks
import random
import datetime
import requests
import os
import feedparser
from threading import Thread
from flask import Flask

# ================= 設定項目 =================
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')
ROLE_ID = 1478266543480766716        
ANNOUNCE_CH_ID = 1476095569595334718 
# 安定していそうなNitterサーバーをいくつか試してください
# RSS_URL = 'https://nitter.privacydev.net/ucg_jp/rss'
# RSS_URL = 'https://nitter.poast.org/ucg_jp/rss'
RSS_URL = 'https://nitter.net/ucg_jp/rss'
KEYWORDS = ['新カード', '公開', '速報', 'メンテナンス', 'カードデザイン']
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG IDを入力してください', placeholder='例: 12345678', min_length=1, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if GAS_URL:
            try: requests.post(GAS_URL, json={"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}, timeout=10)
            except: pass
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

class ConsentView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="c_v5")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("承認されました！", ephemeral=True)
        except: await interaction.response.send_message("エラー：権限不足です。ボットの役職を上げてください。", ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="r_v5")
    async def open_modal(self, it, b): await it.response.send_modal(RegistrationModal())

class RegionButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.regions = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]
    async def update_role(self, it, name):
        guild = it.guild; member = it.user
        to_rem = [discord.utils.get(guild.roles, name=r) for r in self.regions if discord.utils.get(guild.roles, name=r) in member.roles]
        if to_rem: await member.remove_roles(*[r for r in to_rem if r])
        new = discord.utils.get(guild.roles, name=name)
        if new: await member.add_roles(new); await it.response.send_message(f"✅ 「{name}」に設定しました！", ephemeral=True)

    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, custom_id="reg_1")
    async def b1(self, it, b): await self.update_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, custom_id="reg_2")
    async def b2(self, it, b): await self.update_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, custom_id="reg_3")
    async def b3(self, it, b): await self.update_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, custom_id="reg_4")
    async def b4(self, it, b): await self.update_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, custom_id="reg_5")
    async def b5(self, it, b): await self.update_role(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, row=1, custom_id="reg_6")
    async def b6(self, it, b): await self.update_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, row=1, custom_id="reg_7")
    async def b7(self, it, b): await self.update_role(it, "九州・沖縄")

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.guilds = intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        self.last_link = None
        self.active_messages = {}
        self.match_starts = {}

    async def on_ready(self):
        self.add_view(ConsentView()); self.add_view(RegistrationView()); self.add_view(RegionButtons())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'Logged in as {self.user.name}')

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        await self.perform_twitter_check()

    async def perform_twitter_check(self, manual_ctx=None):
        try:
            print(f"Checking RSS: {RSS_URL}")
            feed = feedparser.parse(RSS_URL)
            if not feed.entries:
                msg = "⚠️ Twitter: 記事が見つかりません。URLが死んでいる可能性があります。"
                print(msg)
                if manual_ctx: await manual_ctx.send(msg)
                return

            latest = feed.entries[0]
            if not manual_ctx and self.last_link == latest.link:
                print("新しい投稿なし。")
                return

            title = latest.title
            found = any(k in title for k in KEYWORDS)
            
            if found or manual_ctx:
                ch = self.get_channel(ANNOUNCE_CH_ID)
                if ch:
                    text = f"📢 **Twitter速報**\n{title}\n{latest.link}"
                    if not found and manual_ctx: text += "\n⚠️ (キーワード不一致ですがテスト表示中)"
                    await ch.send(text)
                    print(f"通知送信: {title}")
            
            self.last_link = latest.link
        except Exception as e:
            err = f"❌ Twitterエラー: {e}"
            print(err)
            if manual_ctx: await manual_ctx.send(err)

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            msg = await after.channel.send(f"🎲 **自動割り振り**\n{p1.mention} ⇒ **{roles[0]}**\n{p2.mention} ⇒ **{roles[1]}**", silent=True)
            self.active_messages[after.channel.id] = msg
            self.match_starts[after.channel.id] = {"time": datetime.datetime.now(), "p1": p1.name, "p2": p2.name}
        elif before.channel is not None and len(before.channel.members) < 2:
            if before.channel.id in self.active_messages:
                try: await self.active_messages[before.channel.id].delete()
                except: pass
                del self.active_messages[before.channel.id]
            if before.channel.id in self.match_starts:
                data = self.match_starts.pop(before.channel.id)
                dur = round((datetime.datetime.now() - data["time"]).total_seconds() / 60, 1)
                if GAS_URL:
                    try: requests.post(GAS_URL, json={"type": "match_history", "p1_name": data["p1"], "p2_name
