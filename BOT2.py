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

# 現在比較的安定しているNitterサーバー
RSS_URL = 'https://nitter.privacydev.net/ucg_jp/rss'
KEYWORDS = ['新カード', '公開', '速報', 'メンテナンス', 'カードデザイン']
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- 1. TCG ID登録（3秒ルール/タイムアウト対策済み） ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(
        label='あなたのTCG IDを入力してください',
        placeholder='例: 12345678',
        min_length=1,
        required=True
    )
    async def on_submit(self, interaction: discord.Interaction):
        # タイムアウト回避
        await interaction.response.defer(ephemeral=True)
        if GAS_URL:
            payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
            try: requests.post(GAS_URL, json=payload, timeout=10)
            except: print("GAS送信失敗")
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

# --- 2. 各種ビュー（画像 095821.png, 094447.png 再現） ---
class ConsentView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="consent_v_last")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("承認されました！", ephemeral=True)
        except: await interaction.response.send_message("エラー：権限を確認してください。", ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="reg_v_last")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal())

class RegionButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.regions = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]
    async def update_role(self, it, role_name):
        guild = it.guild; member = it.user
        to_rem = [discord.utils.get(guild.roles, name=r) for r in self.regions if discord.utils.get(guild.roles, name=r) in member.roles]
        if to_rem: await member.remove_roles(*[r for r in to_rem if r])
        new_role = discord.utils.get(guild.roles, name=role_name)
        if new_role:
            await member.add_roles(new_role)
            await it.response.send_message(f"✅ 「{role_name}」に設定しました！", ephemeral=True)

    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, custom_id="reg_1")
    async def r1(self, it, b): await self.update_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, custom_id="reg_2")
    async def r2(self, it, b): await self.update_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, custom_id="reg_3")
    async def r3(self, it, b): await self.update_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, custom_id="reg_4")
    async def r4(self, it, b): await self.update_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, custom_id="reg_5")
    async def r5(self, it, b): await self.update_role(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, row=1, custom_id="reg_6")
    async def r6(self, it, b): await self.update_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, row=1, custom_id="reg_7")
    async def r7(self, it, b): await self.update_role(it, "九州・沖縄")

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
        if not self.check_twitter_task.is_running(): self.check_twitter_task.start()
        print(f'--- {self.user.name} 起動完了 ---')

    @tasks.loop(minutes=15)
    async def check_twitter_task(self):
        await self.perform_check()

    async def perform_check(self, ctx=None):
        now = datetime.datetime.now().strftime('%H:%M:%S')
        print(f"[{now}] Twitterチェック開始: {RSS_URL}")
        try:
            feed = feedparser.parse(RSS_URL)
            if not feed.entries:
                if ctx: await ctx.send("⚠️ 記事が見つかりません。URLが死んでいる可能性があります。")
                return
            latest = feed.entries[0]
            if not ctx and self.last_link == latest.link: return
            
            title = latest.title
            if any(k in title for k in KEYWORDS) or ctx:
                ch = self.get_channel(ANNOUNCE_CH_ID)
                if ch:
                    await ch.send(f"📢 **Twitter速報**\n{title}\n{latest.link}")
            self.last_link = latest.link
        except Exception as e:
            if ctx: await ctx.send(f"❌ エラー: {e}")

bot = MyBot()

# --- 4. コマンド ---
@bot.command()
@commands.has_permissions(administrator=True)
async def tw_check(ctx):
    """手動Twitterチェック"""
    await ctx.send("🔍 Twitterをチェックします...")
    await bot.perform_check(ctx=ctx)

@bot.command()
@commands.has_permissions(administrator=True)
async def rules(ctx):
    emb = discord.Embed(title="✅ 参加の承認", description="上記のルールをすべて読み、同意いただける方は、以下のボタンを押してください。\n押下後、対戦募集チャンネル等の閲覧・書き込みが可能になります。", color=discord.Color.green())
    await ctx.send(embed=emb, view=ConsentView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_roles(ctx):
    emb = discord.Embed(title="地域選択", description="所属地域を選択してください", color=discord.Color.blue())
    await ctx.send(embed=emb, view=RegionButtons())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_registration(ctx):
    emb = discord.Embed(title="📝 TCG IDの登録", description="以下のボタンを押してIDを入力してください。", color=discord.Color.orange())
    await ctx.send(embed=emb, view=RegistrationView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_all(ctx):
    await rules(ctx); await setup_roles(ctx); await setup_registration(ctx)

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
