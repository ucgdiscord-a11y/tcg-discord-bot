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

ROLE_ID = 1478266543480766716        # 参加承認用ロール
ANNOUNCE_CH_ID = 1476095569595334718 # Twitter速報用
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- A. ポイント取得共通処理 ---
async def fetch_user_points(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        res = requests.get(GAS_URL, params={'type': 'get_points', 'user_id': str(interaction.user.id)}, timeout=10)
        data = res.text
        if "NotFound" in data:
            await interaction.followup.send("❌ まだIDが登録されていません。「📝 TCG IDを登録する」ボタンから登録してください。", ephemeral=True)
        else:
            await interaction.followup.send(f"🏆 **{interaction.user.display_name}** さんの現在の累計ポイントは **{data}pt** です！", ephemeral=True)
    except:
        await interaction.followup.send("⚠️ 通信エラーが発生しました。時間をおいて試してください。", ephemeral=True)

# --- B. TCG ID登録モーダル ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678', min_length=1)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
        try:
            requests.post(GAS_URL, json=payload, timeout=10)
            await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)
        except:
            await interaction.followup.send("⚠️ 登録に失敗しました。", ephemeral=True)

# --- C. 各コマンド専用の View 定義 ---

# 1. 承認パネル専用 (!rules)
class RulesOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="v8_agree")
    async def agree(self, it, b):
        role = it.guild.get_role(ROLE_ID)
        try:
            await it.user.add_roles(role)
            await it.response.send_message("承認されました！", ephemeral=True)
        except: await it.response.send_message("❌ エラー：ボットの役職順位を上げてください。", ephemeral=True)

# 2. ID登録パネル専用 (!setup_registration)
class RegistrationOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.secondary, custom_id="v8_reg")
    async def reg(self, it, b): await it.response.send_modal(RegistrationModal())

# 3. ポイント確認パネル専用 (!setup_points)
class PointsOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🏆 累計ポイントを確認する", style=discord.ButtonStyle.primary, custom_id="v8_pts")
    async def check(self, it, b): await fetch_user_points(it)

# 4. 地域選択パネル専用 (!setup_roles)
class RegionButtonsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.regions = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]
    async def update_role(self, it, name):
        guild = it.guild; member = it.user
        to_rem = [discord.utils.get(guild.roles, name=r) for r in self.regions if discord.utils.get(guild.roles, name=r) in member.roles]
        if to_rem: await member.remove_roles(*[r for r in to_rem if r])
        new = discord.utils.get(guild.roles, name=name)
        if new:
            await member.add_roles(new)
            await it.response.send_message(f"✅ 「{name}」に設定しました！", ephemeral=True)
        else: await it.response.send_message(f"❌ 役職「{name}」が未作成です。", ephemeral=True)

    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, custom_id="r1")
    async def b1(self, it, b): await self.update_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, custom_id="r2")
    async def b2(self, it, b): await self.update_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, custom_id="r3")
    async def b3(self, it, b): await self.update_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, custom_id="r4")
    async def b4(self, it, b): await self.update_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, custom_id="r5")
    async def b5(self, it, b): await self.update_role(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, row=1, custom_id="r6")
    async def b6(self, it, b): await self.update_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, row=1, custom_id="r7")
    async def b7(self, it, b): await self.update_role(it, "九州・沖縄")

# --- D. ボット本体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.guilds
