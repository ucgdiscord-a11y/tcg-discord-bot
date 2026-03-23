import discord
from discord.ext import commands, tasks
import random
import requests
import datetime
import os
import sys
import feedparser
from threading import Thread
from flask import Flask

# ================= 設定項目 =================
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')
ROLE_ID = 1478266543480766716        # 参加承認ロール
ANNOUNCE_CH_ID = 1476095569595334718 # 速報・誘導用チャンネル
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask():
    try: app.run(host='0.0.0.0', port=10000)
    except: pass

# --- ポイント確認 ---
async def fetch_user_points(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        res = requests.get(GAS_URL, params={'type': 'get_points', 'user_id': str(interaction.user.id)}, timeout=10)
        data = res.text
        if "NotFound" in data:
            await interaction.followup.send("❌ まだIDが登録されていません。「📝 TCG IDを登録する」から登録してください。", ephemeral=True)
        else:
            await interaction.followup.send(f"🏆 **{interaction.user.display_name}** さんの現在の累計ポイントは **{data}pt** です！", ephemeral=True)
    except: await interaction.followup.send("⚠️ GASとの通信エラーが発生しました。", ephemeral=True)

# --- 登録モーダル ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678', min_length=1)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = {"type": "register", "user_id": str(interaction.user.id), "user_name": interaction.user.display_name, "tcg_id": self.tcg_id_input.value}
        try:
            requests.post(GAS_URL, json=payload, timeout=10)
            await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)
        except: await interaction.followup.send("⚠️ スプレッドシートへの登録に失敗しました。", ephemeral=True)

# --- UI View群 ---
class RulesOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="v16_agree")
    async def agree(self, it, b):
        role = it.guild.get_role(ROLE_ID)
        try:
            await it.user.add_roles(role)
            await it.response.send_message("承認されました！全機能が解放されました。", ephemeral=True)
        except: await it.response.send_message("❌ ボットの役職を一番上に上げてください。", ephemeral=True)

class RegistrationOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="v16_reg")
    async def reg(self, it, b): await it.response.send_modal(RegistrationModal())

class PointsOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🏆 累計ポイントを確認する", style=discord.ButtonStyle.primary, custom_id="v16_pts")
    async def check(self, it, b): await fetch_user_points(it)

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
            await it.response.send_message(f"✅ 所属を「{name}」に変更しました！", ephemeral=True)
        else: await it.response.send_message(f"❌ 役職「{name}」未作成。", ephemeral=True)
    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, custom_id="v16_r1")
    async def b1(self, it, b): await self.update_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, custom_id="v16_r2")
    async def b2(self, it, b): await self.update_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, custom_id="v16_r3")
    async def b3(self, it, b): await self.update_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, custom_id="v16_r4")
    async def b4(self, it, b): await self.update_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, custom_id="v16_r5")
    async def b5(self, it, b): await self.update_role(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, row=1, custom_id="v16_r6")
    async def b6(self, it, b): await self.update_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, row=1, custom_id="v16_r7")
    async def b7(self, it, b): await self.update_role(it, "九州・沖縄")

# --- メイン ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        self.match_starts = {}
        self.last_twitter_link = None

    async def on_ready(self):
        self.add_view(RulesOnlyView()); self.add_view(RegistrationOnlyView())
        self.add_view(PointsOnlyView()); self.add_view(RegionButtonsView())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'✅ ログイン成功: {self.user.name} (V16 Twitter+Manual Full)')

    # 1. 参加誘導
    async def on_member_join(self, member):
        ch = self.get_channel(ANNOUNCE_CH_ID)
        if ch: await ch.send(f"👋 **{member.mention} さん、ようこそ！**\n「各種登録事項」チャンネルでID登録と規約同意をお願いします！")

    # 2. Twitter監視 (RSS)
    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            res = requests.get(GAS_URL, params={'type': 'fetch_rss'}, timeout=20)
            feed = feedparser.parse(res.text)
            if not feed.entries: return
            latest = feed.entries[0]
            if self.last_twitter_link == latest.link: return
            keywords = ['カードデザイン', '公開', '新カード']
            if any(k in latest.title for k in keywords):
                ch = self.get_channel(ANNOUNCE_CH_ID)
                if ch: await ch.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
            self.last_twitter_link = latest.link
        except: pass

    # 3. 対戦サポート (VC)
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            self.match_starts[after.channel.id] = {"time": datetime.datetime.now(), "p1_id": p1.id, "p2_id": p2.id, "p1_name": p1.name, "p2_name": p2.name}
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            await after.channel.send(f"🎲 **自動割り振り**\n**{p1.display_name}** ⇒ **{roles[0]}**\n**{p2.display_name}** ⇒ **{roles[1]}**", silent=True, delete_after=60)
        elif before.channel is not None and len(before.channel.members) < 2:
            if before.channel.id in self.match_starts:
                d = self.match_starts.pop(before.channel.id)
                dur = round((datetime.datetime.now() - d["time"]).total_seconds() / 60, 1)
                requests.post(GAS_URL, json={"type": "match_pending", "p1_id": str(d["p1_id"]), "p1_name": d["p1_name"], "p2_id": str(d["p2_id"]), "p2_name": d["p2_name"], "duration": f"{dur}分", "channel": before.channel.name}, timeout=10)

bot = MyBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_all(ctx):
    await ctx.send(embed=discord.Embed(title="✅ 参加承認", color=discord.Color.green()), view=RulesOnlyView())
    await ctx.send(embed=discord.Embed(title="📝 TCG IDの登録", description="TCG IDを登録してください", color=discord.Color.blue()), view=RegistrationOnlyView())
    await ctx.send(embed=discord.Embed(title="🏆 ポイント確認", color=discord.Color.blue()), view=PointsOnlyView())
    await ctx.send(embed=discord.Embed(title="📍 地域選択", description="所属地域を選択してください", color=discord.Color.blue()), view=RegionButtonsView())

if __name__ == "__main__":
    Thread(target=run_flask).start()
    try: bot.run(TOKEN)
    except Exception as e: print(f"❌ 起動エラー: {e}")
