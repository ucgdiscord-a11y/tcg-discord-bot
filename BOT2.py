ご提示いただいたコード、しっかり確認しました！このコードには、これまでのやり取りで重視してきた 「VC対戦の自動割り振り（サイレント通知）」 や 「重複ロールの自動削除」 といった非常に重要なロジックがすべて組み込まれていますね。

ただ、このコードをそのまま Render などのサーバーで動かすには、あと一歩だけ 「居眠り防止（Flaskサーバー）」 と 「セキュリティ（環境変数）」 の設定を足すのがベストです。

それらをすべて合体させ、GitHubに貼り付けるだけで完結する 【究極の統合版】 を作成しました！

🚀 BOT2.py：すべての機能を1つに（決定版）
このコードは、ご提示いただいた「高度なVC処理」と「地域管理」を100%継承しつつ、サーバーで24時間動かすための設定を追加したものです。

Python
import discord
from discord.ext import commands, tasks
import random
import datetime
import requests
import os
import feedparser
from threading import Thread
from flask import Flask

# ================= 設定項目（環境変数から読み込み） =================
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')
ROLE_ID = 1478266543480766716        # メンバー役職ID
ANNOUNCE_CH_ID = 1476095569595334718 # Twitter通知用
WELCOME_CH_ID = 1464168951012393021  # 挨拶用
RSS_URL = 'https://nitter.perennialte.ch/ucg_jp/rss'
KEYWORDS = ['カードデザイン', '公開', '新カード']
# ==============================================================

# Renderの居眠り防止用（Flask）
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask(): app.run(host='0.0.0.0', port=8080)

# --- 1. TCG ID登録用（モーダル & ビュー） ---
class RegistrationModal(discord.ui.Modal, title='TCG IDの登録'):
    tcg_id_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678', min_length=1, required=True)
    async def on_submit(self, interaction: discord.Interaction):
        if GAS_URL:
            payload = {"type": "register", "user_id": str(interaction.user.id), "tcg_id": self.tcg_id_input.value}
            try: requests.post(GAS_URL, json=payload)
            except: pass
        await interaction.response.send_message(f"✅ IDを登録しました！", ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="reg_modal_btn_sep")
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModal())

# --- 2. 承認用（ビュー） ---
class ConsentView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="consent_btn")
    async def agree(self, interaction: discord.Interaction, button: discord.ui.Button):
        role = interaction.guild.get_role(ROLE_ID)
        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("承認されました！", ephemeral=True)
        except: await interaction.response.send_message("エラー：権限を確認してください。", ephemeral=True)

# --- 3. 地域選択用（重複削除ロジック付き） ---
class RegionButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.regions = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]

    async def update_role(self, interaction: discord.Interaction, target_role_name: str):
        guild = interaction.guild
        member = interaction.user
        # 他の地域ロールを持っていたら削除
        roles_to_remove = [discord.utils.get(guild.roles, name=r) for r in self.regions if discord.utils.get(guild.roles, name=r) in member.roles]
        if roles_to_remove: 
            valid_roles = [r for r in roles_to_remove if r is not None]
            await member.remove_roles(*valid_roles)
        
        new_role = discord.utils.get(guild.roles, name=target_role_name)
        if new_role:
            await member.add_roles(new_role)
            await interaction.response.send_message(f"✅ 「{target_role_name}」に設定しました！", ephemeral=True)

    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.primary, row=0, custom_id="reg_tohoku")
    async def tohoku(self, it, btn): await self.update_role(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, row=0, custom_id="reg_kanto")
    async def kanto(self, it, btn): await self.update_role(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.primary, row=0, custom_id="reg_hokushinetsu")
    async def hokushinetsu(self, it, btn): await self.update_role(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.primary, row=0, custom_id="reg_chubu")
    async def chubu(self, it, btn): await self.update_role(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.primary, row=0, custom_id="reg_kansai")
    async def kansai(self, it, btn): await self.update_role(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.primary, row=1, custom_id="reg_shikoku")
    async def shikoku_chugoku(self, it, btn): await self.update_role(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.primary, row=1, custom_id="reg_kyushu")
    async def kyushu_okinawa(self, it, btn): await self.update_role(it, "九州・沖縄")

# --- 4. ボット本体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.guilds = intents.voice_states = intents.reactions = True
        super().__init__(command_prefix='!', intents=intents)
        self.active_messages = {}
        self.last_link = None
        self.match_starts = {}

    async def on_ready(self):
        self.add_view(ConsentView())
        self.add_view(RegistrationView())
        self.add_view(RegionButtons())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'Logged in as {self.user.name}')

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            feed = feedparser.parse(RSS_URL)
            if not feed.entries: return
            latest = feed.entries[0]
            if self.last_link == latest.link: return
            if any(k in latest.title for k in KEYWORDS):
                channel = self.get_channel(ANNOUNCE_CH_ID)
                if channel: await channel.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
            self.last_link = latest.link
        except Exception as e: print(f"Twitterエラー: {e}")

    async def on_voice_state_update(self, member, before, after):
        # 2人揃った時
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            msg = await after.channel.send(
                f"🎲 **自動割り振り**\n{p1.mention} ⇒ **{roles[0]}**\n{p2.mention} ⇒ **{roles[1]}**",
                silent=True
            )
            self.active_messages[after.channel.id] = msg
            self.match_starts[after.channel.id] = {"time": datetime.datetime.now(), "p1": p1.name, "p2": p2.name}

        # 誰かが抜けた時
        elif before.channel is not None and len(before.channel.members) < 2:
            if before.channel.id in self.active_messages:
                try: await self.active_messages[before.channel.id].delete()
                except: pass
                del self.active_messages[before.channel.id]
            
            if before.channel.id in self.match_starts:
                data = self.match_starts.pop(before.channel.id)
                duration_min = round((datetime.datetime.now() - data["time"]).total_seconds() / 60, 1)
                if GAS_URL:
                    payload = {
                        "type": "match_history", "p1_name": data["p1"], "p2_name": data["p2"],
                        "duration": f"{duration_min}分", "channel": before.channel.name
                    }
                    try: requests.post(GAS_URL, json=payload)
                    except: pass

bot = MyBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_all(ctx):
    """すべてのパネルを一括設置"""
    await ctx.send(embed=discord.Embed(title="✅ 承認", description="ボタンを押してください。", color=discord.Color.green()), view=ConsentView())
    await ctx.send(embed=discord.Embed(title="🌍 地域選択", description="地域を選んでください。", color=discord.Color.blue()), view=RegionButtons())
    await ctx.send(embed=discord.Embed(title="📝 ID登録", description="青いボタンからどうぞ。", color=discord.Color.orange()), view=RegistrationView())

if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(TOKEN)
