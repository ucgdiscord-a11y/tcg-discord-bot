import discord
from discord.ext import commands, tasks
import random
import feedparser
import requests
import datetime
import os
import time
from threading import Thread
from flask import Flask

# ================= 設定項目 =================
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')

ROLE_ID = 1478266543480766716
ANNOUNCE_CH_ID = 1476095569595334718

# ★ 現在、クラウドIPからでも比較的「返事」を返してくれるサーバーを厳選
RSS_URLS = [
    'https://nitter.privacydev.net/ucg_jp/rss',
    'https://nitter.poast.org/ucg_jp/rss',
    'https://nitter.uni-sonia.com/ucg_jp/rss',
    'https://nitter.x86-64-unknown-linux-gnu.zip/ucg_jp/rss'
]
KEYWORDS = ['カードデザイン', '公開', '新カード']
# ===========================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# --- ID登録モーダル ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678', min_length=1, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            requests.post(GAS_URL, json={"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}, timeout=10)
        except: pass
        await interaction.followup.send(f"✅ ID: `{self.tcg_id_input.value}` を登録しました！", ephemeral=True)

# --- ボタンビュー ---
class MainViews(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="c_v8")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("承認されました！", ephemeral=True)
        except: await interaction.response.send_message("エラー：役職の順序を確認してください。", ephemeral=True)

    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="r_v8")
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

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        self.last_link = None
        self.active_messages = {}
        self.match_starts = {}

    async def on_ready(self):
        self.add_view(MainViews()); self.add_view(RegionButtons())
        if not self.check_twitter_task.is_running(): self.check_twitter_task.start()
        print(f'Logged in as {self.user.name}')

    @tasks.loop(minutes=15)
    async def check_twitter_task(self):
        await self.perform_check()

    async def perform_check(self, ctx=None):
        # 通信のヘッダーをさらに詳細にして「人間味」を出す
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8'
        }
        
        for url in RSS_URLS:
            try:
                # タイムアウトを少し長めに設定
                response = requests.get(url, headers=headers, timeout=20)
                if response.status_code != 200:
                    print(f"URL失敗 ({response.status_code}): {url}")
                    continue
                
                feed = feedparser.parse(response.content)
                if not feed.entries:
                    print(f"記事空っぽ: {url}")
                    continue
                
                latest = feed.entries[0]
                if not ctx and self.last_link == latest.link: return
                
                title = latest.title
                if any(k in title for k in KEYWORDS) or ctx:
                    ch = self.get_channel(ANNOUNCE_CH_ID)
                    if ch: await ch.send(f"📢 **Twitter速報**\n{title}\n{latest.link}")
                
                self.last_link = latest.link
                if ctx: await ctx.send(f"✅ 取得成功: {url}")
                return # どこか一つ成功すれば終了
            except Exception as e:
                print(f"接続エラー ({url}): {e}")
                time.sleep(2) # 少し待ってから次のURLへ
                continue
        
        if ctx: await ctx.send("❌ 全ての取得先から拒否されました。RenderのIPが制限されているようです。")

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
                try: requests.post(GAS_URL, json={"type": "match_history", "p1_name": data["p1"], "p2_name": data["p2"], "duration": f"{dur}分", "channel": before.channel.name}, timeout=5)
                except: pass

bot = MyBot()

@bot.command()
async def tw_check(ctx):
    await ctx.send("🔍 最終チェックを開始します...")
    await bot.perform_check(ctx=ctx)

@bot.command()
async def setup_all(ctx):
    emb = discord.Embed(title="✅ 参加の承認", description="上記のルールをすべて読み、同意いただける方は、以下のボタンを押してください。\n押下後、対戦募集チャンネル等の閲覧・書き込みが可能になります。", color=discord.Color.green())
    await ctx.send(embed=emb, view=MainViews())
    await ctx.send(embed=discord.Embed(title="地域選択", description="所属地域を選択してください", color=discord.Color.blue()), view=RegionButtons())

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
