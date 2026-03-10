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
ROLE_ID = 1478266543480766716        # 承認時に付与する役職ID
ANNOUNCE_CH_ID = 1476095569595334718 # Twitter速報用
RSS_URL = 'https://nitter.perennialte.ch/ucg_jp/rss'
KEYWORDS = ['新カード', '公開', '速報', 'メンテナンス', 'カードデザイン']
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- 1. TCG ID登録モーダル（3秒ルール対策） ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(
        label='あなたのTCG IDを入力してください',
        placeholder='例: 12345678',
        min_length=1,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) # タイムアウト回避
        if GAS_URL:
            payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
            try: requests.post(GAS_URL, json=payload, timeout=10)
            except: pass
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

# --- 2. 各種ボタンビュー ---
class ConsentView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="consent_btn_v_final")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("承認されました！", ephemeral=True)
        except:
            await interaction.response.send_message("エラー：ボットの役職をメンバーより上に上げてください。", ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="reg_id_btn_sep")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal())

class RegionButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.regions = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]

    async def update_role(self, interaction: discord.Interaction, target_role_name: str):
        guild = interaction.guild
        member = interaction.user
        roles_to_remove = [discord.utils.get(guild.roles, name=r) for r in self.regions if discord.utils.get(guild.roles, name=r) in member.roles]
        if roles_to_remove: await member.remove_roles(*[r for r in roles_to_remove if r])
        new_role = discord.utils.get(guild.roles, name=target_role_name)
        if new_role:
            await member.add_roles(new_role)
            await interaction.response.send_message(f"✅ 「{target_role_name}」に設定しました！", ephemeral=True)

    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, row=0, custom_id="reg_1")
    async def tohoku(self, it, btn): await self.update_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, row=0, custom_id="reg_2")
    async def kanto(self, it, btn): await self.update_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, row=0, custom_id="reg_3")
    async def hokushinetsu(self, it, btn): await self.update_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, row=0, custom_id="reg_4")
    async def chubu(self, it, btn): await self.update_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, row=0, custom_id="reg_5")
    async def kansai(self, it, btn): await self.update_role(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, row=1, custom_id="reg_6")
    async def shikoku(self, it, btn): await self.update_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, row=1, custom_id="reg_7")
    async def kyushu(self, it, btn): await self.update_role(it, "九州・沖縄")

# --- 3. ボット本体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.guilds = intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        self.active_messages = {}
        self.last_link = None
        self.match_starts = {}

    async def on_ready(self):
        self.add_view(ConsentView()); self.add_view(RegistrationView()); self.add_view(RegionButtons())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'Logged in as {self.user.name}')

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            feed = feedparser.parse(RSS_URL)
            if not feed.entries: return
            latest = feed.entries[0]
            if self.last_link != latest.link and any(k in latest.title for k in KEYWORDS):
                ch = self.get_channel(ANNOUNCE_CH_ID)
                if ch: await ch.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
                self.last_link = latest.link
        except: pass

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
                    payload = {"type": "match_history", "p1_name": data["p1"], "p2_name": data["p2"], "duration": f"{dur}分", "channel": before.channel.name}
