import discord
from discord.ext import commands, tasks
import random
import datetime
import requests
import os
import feedparser
from threading import Thread
from flask import Flask

# ================= config (現在の設定を維持) =================
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')
ANNOUNCE_CH_ID = 1476095569595334718 
WELCOME_CH_ID = 1464168951012393021
ROLE_ID = 1478266543480766716
RSS_URL = 'https://nitter.perennialte.ch/ucg_jp/rss' 
KEYWORDS = ['カードデザイン', '公開', '新カード', '速報', 'メンテナンス']
# ==========================================================

# Render維持用Flask設定
app = Flask('')
@app.route('/')
def home(): return "Bot is Alive!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- 1. TCG ID入力用フォーム（モーダル） ---
class TCGIdModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id = discord.ui.TextInput(
        label='あなたのTCG IDを入力してください',
        placeholder='例: 12345678',
        min_length=5, max_length=15, required=True
    )
    async def on_submit(self, interaction: discord.Interaction):
        if GAS_URL:
            # GUS(GAS)へデータを送信
            data = {"type": "id_registration", "user": interaction.user.name, "tcg_id": self.tcg_id.value}
            try: requests.post(GAS_URL, json=data)
            except: pass
        await interaction.response.send_message(f'✅ ID: `{self.tcg_id.value}` を登録しました！', ephemeral=True)

# --- 2. 地域ボタンとID登録ボタンのパネル ---
class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def assign_role(self, interaction, role_name):
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ {role_name} ロールを付与しました！", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ '{role_name}' ロールが見つかりません。", ephemeral=True)

    # 1段目：地域ボタン
    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, custom_id="reg_tohoku")
    async def tohoku(self, it, bt): await self.assign_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, custom_id="reg_kanto")
    async def kanto(self, it, bt): await self.assign_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, custom_id="reg_hokushinetsu")
    async def hokushinetsu(self, it, bt): await self.assign_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, custom_id="reg_chubu")
    async def chubu(self, it, bt): await self.assign_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, custom_id="reg_kansai")
    async def kansai(self, it, bt): await self.assign_role(it, "関西")
    
    # 2段目：地域ボタン続き
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, custom_id="reg_shikoku", row=1)
    async def shikoku(self, it, bt): await self.assign_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, custom_id="reg_kyushu", row=1)
    async def kyushu(self, it, bt): await self.assign_role(it, "九州・沖縄")

    # 3段目：ID登録
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="reg_id_btn", row=2)
    async def register_id(self, it, bt):
        await it.response.send_modal(TCGIdModal())

# --- 3. ボット本体のロジック ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.guilds = intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        self.last_url = None

    async def on_ready(self):
        print(f'Logged in as {self.user.name}')
        self.add_view(RegistrationView()) # ボタンを永続化
        if not self.check_twitter.is_running(): self.check_twitter.start()

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            feed = feedparser.parse(RSS_URL)
            if feed.entries:
                latest = feed.entries[0]
                if latest.link != self.last_url and any(k in latest.title for k in KEYWORDS):
                    ch = self.get_channel(ANNOUNCE_CH_ID)
                    if ch:
                        await ch.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
                        self.last_url = latest.link
        except: pass

    async def on_voice_state_update(self, member, before, after):
        # 2人揃ったらダイス
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            await after.channel.send(f"🎲 **対戦準備**\n{p1.mention}⇒{roles[0]}\n{p2.mention}⇒{roles[1]}")

bot = MyBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_panel(ctx):
    # スクリーンショット通りの2枚の埋め込みを作成
    emb1 = discord.Embed(title="地域選択", description="所属地域を選択してください", color=discord.Color.blue())
    emb2 = discord.Embed(title="📝 TCG IDの登録", description="以下のボタンを押してIDを入力してください。", color=discord.Color.orange())
    await ctx.send(embeds=[emb1, emb2], view=RegistrationView())

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
