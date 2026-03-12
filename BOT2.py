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

ROLE_ID = 1478266543480766716        # 参加承認用ロールID
ANNOUNCE_CH_ID = 1476095569595334718 # 速報用チャンネルID
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- A. 共通処理 (ポイント取得) ---
async def fetch_user_points(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        res = requests.get(GAS_URL, params={'type': 'get_points', 'user_id': str(interaction.user.id)}, timeout=10)
        data = res.text
        if "NotFound" in data:
            await interaction.followup.send("❌ まだIDが登録されていません。「📝 TCG IDを登録する」ボタンから登録してください。", ephemeral=True)
        else:
            await interaction.followup.send(f"🏆 **{interaction.user.display_name}** さんの累計ポイントは **{data}pt** です！", ephemeral=True)
    except:
        await interaction.followup.send("⚠️ エラー：スプレッドシートとの通信に失敗しました。", ephemeral=True)

# --- B. モーダル (ID登録入力画面) ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678', min_length=1)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
        try:
            requests.post(GAS_URL, json=payload, timeout=10)
            await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)
        except:
            await interaction.followup.send("⚠️ 登録に失敗しました。時間をおいて試してください。", ephemeral=True)

# --- C. ボタン View 定義 ---

# 1. 地域選択
class RegionButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.regions = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]
    
    async def update_role(self, it, name):
        guild = it.guild; member = it.user
        to_rem = [discord.utils.get(guild.roles, name=r) for r in self.regions if discord.utils.get(guild.roles, name=r) in member.roles]
        if to_rem: await member.remove_roles(*[r for r in to_rem if r])
        new = discord.utils.get(guild.roles, name=name)
        if new:
            try:
                await member.add_roles(new)
                await it.response.send_message(f"✅ 「{name}」に設定しました！", ephemeral=True)
            except: await it.response.send_message("❌ エラー：ボットの役職順位を上げてください。", ephemeral=True)
        else: await it.response.send_message(f"❌ エラー：役職「{name}」が未作成です。", ephemeral=True)

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

# 2. ポイント確認単体
class PointsOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🏆 累計ポイントを確認する", style=discord.ButtonStyle.primary, custom_id="pts_v7")
    async def check(self, it, b): await fetch_user_points(it)

# 3. ID登録単体
class RegisterOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.secondary, custom_id="reg_v7")
    async def reg(self, it, b): await it.response.send_modal(RegistrationModal())

# 4. メインパネル (承認・登録・ポイント)
class MainViews(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="agree_v7")
    async def agree(self, it, b):
        role = it.guild.get_role(ROLE_ID)
        try:
            await it.user.add_roles(role)
            await it.response.send_message("承認されました！", ephemeral=True)
        except: await it.response.send_message("❌ エラー：ボットの役職順位を上げてください。", ephemeral=True)
    
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.secondary, custom_id="reg_main_v7")
    async def reg(self, it, b): await it.response.send_modal(RegistrationModal())

    @discord.ui.button(label="🏆 累計ポイントを確認する", style=discord.ButtonStyle.primary, custom_id="pts_main_v7")
    async def check(self, it, b): await fetch_user_points(it)

# --- D. ボット本体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True # コマンド読み取りに必須
        intents.members = True         # 役職操作に必須
        intents.voice_states = True    # VC連動に必須
        super().__init__(command_prefix='!', intents=intents)
        self.match_starts = {}
        self.last_link = None

    async def on_ready(self):
        # 永続ボタンの登録（再起動しても動くようにする）
        self.add_view(MainViews())
        self.add_view(RegionButtons())
        self.add_view(PointsOnlyView())
        self.add_view(RegisterOnlyView())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'Logged in as {self.user.name} - All Commands Loaded')

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            res = requests.get(GAS_URL, params={'type': 'fetch_rss'}, timeout=20)
            feed = feedparser.parse(res.text)
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
        # 対戦開始：2人揃ったら通知（60秒で削除）
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            self.match_starts[after.channel.id] = {
                "time": datetime.datetime.now(), "p1_name": p1.name, "p2_name": p2.name, "p1_id": p1.id, "p2_id": p2.id
            }
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            await after.channel.send(
                f"🎲 **自動割り振り**\n**{p1.display_name}** ⇒ **{roles[0]}**\n**{p2.display_name}** ⇒ **{roles[1]}**", 
                silent=True, delete_after=60
            )
        # 対戦終了：裏側でスプシ送信のみ
        elif before.channel is not None and len(before.channel.members) < 2:
            if before.channel.id in self.match_starts:
                data = self.match_starts.pop(before.channel.id)
                dur = round((datetime.datetime.now() - data["time"]).total_seconds() / 60, 1)
                requests.post(GAS_URL, json={
                    "type": "match_pending", "p1_id": str(data["p1_id"]), "p1_name": data["p1_name"],
                    "p2_id": str(data["p2_id"]), "p2_name": data["p2_name"], 
                    "duration": f"{dur}分", "channel": before.channel.name
                })

bot = MyBot()

# --- E. 管理者コマンド (!setup_...) ---

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_all(ctx):
    """【全部入り】承認・登録・ポイント ＋ 地域選択"""
    await ctx.send(embed=discord.Embed(title="🎮 サーバー初期設定", description="下のボタンから各登録とポイント確認ができます。", color=discord.Color.green()), view=MainViews())
    await ctx.send(embed=discord.Embed(title="📍 地域選択", description="所属地域を選択してください。", color=discord.Color.blue()), view=RegionButtons())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    """【地域のみ】"""
    await ctx.send(embed=discord.Embed(title="📍 地域選択", description="ボタンを押すと役職が付与されます。", color=discord.Color.blue()), view=RegionButtons())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_points(ctx):
    """【ポイントのみ】"""
    await ctx.send(embed=discord.Embed(title="🏆 ポイント確認", color=discord.Color.blue()), view=PointsOnlyView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_registration(ctx):
    """【登録のみ】"""
    await ctx.send(embed=discord.Embed(title="📝 TCG IDの登録", color=discord.Color.orange()), view=RegisterOnlyView())

@bot.command()
@commands.has_permissions(administrator=True)
async def rules(ctx):
    """【承認＋登録】"""
    await ctx.send(embed=discord.Embed(
