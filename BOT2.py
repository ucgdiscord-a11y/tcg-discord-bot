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
GAS_URL = os.getenv('GAS_URL') # Renderの環境変数に設定したGASのURL

ROLE_ID = 1478266543480766716
ANNOUNCE_CH_ID = 1476095569595334718
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ID登録モーダル ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG IDを入力してください', placeholder='例: 12345678', min_length=1, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
        try: requests.post(GAS_URL, json=payload, timeout=10)
        except: pass
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

# --- ボタンビュー ---
class MainViews(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="v9_c")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("承認されました！", ephemeral=True)
        except: await interaction.response.send_message("エラー：役職の順序を確認してください。", ephemeral=True)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="v9_r")
    async def register(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal())

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
    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, custom_id="b1")
    async def b1(self, it, b): await self.update_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, custom_id="b2")
    async def b2(self, it, b): await self.update_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, custom_id="b3")
    async def b3(self, it, b): await self.update_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, custom_id="b4")
    async def b4(self, it, b): await self.update_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, custom_id="b5")
    async def b5(self, it, b): await self.update_role(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, row=1, custom_id="b6")
    async def b6(self, it, b): await self.update_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, row=1, custom_id="b7")
    async def b7(self, it, b): await self.update_role(it, "九州・沖縄")

# --- ボット本体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        self.last_link = None
        self.active_messages = {}
        self.match_starts = {}

    async def on_ready(self):
        self.add_view(MainViews()); self.add_view(RegionButtons())
        if not self.check_twitter_task.is_running(): self.check_twitter_task.start()
        print(f'--- {self.user.name} 起動完了 (GAS Proxy Mode) ---')

    @tasks.loop(minutes=15)
    async def check_twitter_task(self):
        await self.perform_check()

    async def perform_check(self, ctx=None):
        try:
            # ★ ここが重要！直接Twitterを見に行かず、GASに「取ってきて」と頼む
            response = requests.get(GAS_URL, params={'type': 'fetch_rss'}, timeout=20)
            
            if response.status_code != 200:
                if ctx: await ctx.send(f"❌ GASが拒否されました。GASのデプロイ設定を確認してください。")
                return

            feed = feedparser.parse(response.text)
            if not feed.entries:
                if ctx: await ctx.send("❌ GASは動いていますが、Twitter情報が空でした。")
                return
            
            latest = feed.entries[0]
            if not ctx and self.last_link == latest.link: return
            
            # キーワードチェック
            keywords = ['カードデザイン', '公開', '新カード']
            if any(k in latest.title for k in keywords) or ctx:
                ch = self.get_channel(ANNOUNCE_CH_ID)
                if ch: await ch.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
            
            self.last_link = latest.link
            if ctx: await ctx.send("✅ GAS経由で取得成功！")
        except Exception as e:
            if ctx: await ctx.send(f"⚠️ エラー: {e}")

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
                requests.post(GAS_URL, json={"type": "match_history", "p1_name": data["p1"], "p2_name": data["p2"], "duration": f"{dur}分", "channel": before.channel.name})

bot = MyBot()

@bot.command()
async def tw_check(ctx):
    await ctx.send("🔍 GAS経由でチェックを開始します...")
    await bot.perform_check(ctx=ctx)

@bot.command()
async def setup_all(ctx):
    await ctx.send(embed=discord.Embed(title="✅ 参加の承認", description="ボタンを押してください。", color=discord.Color.green()), view=MainViews())
    await ctx.send(embed=discord.Embed(title="地域選択", description="地域を選んでください。", color=discord.Color.blue()), view=RegionButtons())

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
