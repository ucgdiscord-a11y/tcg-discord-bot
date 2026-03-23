import discord
from discord.ext import commands, tasks
import requests
import os
import sys
import feedparser
from threading import Thread
from flask import Flask
import datetime
import random

# ================= 設定（環境変数から読み込み） =================
TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')
ROLE_ID = 1478266543480766716
ANNOUNCE_CH_ID = 1476095569595334718
# =============================================================

app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"

def run_flask():
    try:
        port = int(os.environ.get("PORT", 10000))
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        print(f"❌ Flask起動エラー: {e}")

# --- View群 (資料通りの設定) ---
class RulesOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="v17_agree")
    async def agree(self, it, b):
        role = it.guild.get_role(ROLE_ID)
        try:
            await it.user.add_roles(role)
            await it.response.send_message("承認されました！", ephemeral=True)
        except: await it.response.send_message("❌ 役職エラー。ボットの役職を一番上にしてください。", ephemeral=True)

class RegistrationOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="v17_reg")
    async def reg(self, it, b):
        modal = discord.ui.Modal(title='TCG IDの登録')
        tcg_id_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678')
        async def on_submit(it_modal):
            await it_modal.response.defer(ephemeral=True)
            requests.post(GAS_URL, json={"type": "register", "user_id": str(it_modal.user.id), "user_name": it_modal.user.display_name, "tcg_id": tcg_id_input.value})
            await it_modal.followup.send(f"✅ ID: `{tcg_id_input.value}` を登録しました！", ephemeral=True)
        modal.on_submit = on_submit
        modal.add_item(tcg_id_input)
        await it.response.send_modal(modal)

class PointsOnlyView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🏆 累計ポイントを確認する", style=discord.ButtonStyle.primary, custom_id="v17_pts")
    async def check(self, it, b):
        await it.response.defer(ephemeral=True)
        res = requests.get(GAS_URL, params={'type': 'get_points', 'user_id': str(it.user.id)})
        await it.followup.send(f"🏆 現在の累計ポイントは **{res.text}pt** です！", ephemeral=True)

class RegionButtonsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.regions = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]
    async def update_role(self, it, name):
        to_rem = [discord.utils.get(it.guild.roles, name=r) for r in self.regions if discord.utils.get(it.guild.roles, name=r) in it.user.roles]
        if to_rem: await it.user.remove_roles(*[r for r in to_rem if r])
        new = discord.utils.get(it.guild.roles, name=name)
        if new: await it.user.add_roles(new); await it.response.send_message(f"✅ {name}に設定！", ephemeral=True)

    @discord.ui.button(label="関東", style=discord.ButtonStyle.primary, custom_id="v17_r2")
    async def b2(self, it, b): await self.update_role(it, "関東")
    # ※ 他の地域ボタンも同様に配置（ここではコード短縮のため省略）

# --- ボット本体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.voice_states = True
        super().__init__(command_prefix='!', intents=intents)
        self.last_link = None

    async def on_ready(self):
        self.add_view(RulesOnlyView()); self.add_view(RegistrationOnlyView())
        self.add_view(PointsOnlyView()); self.add_view(RegionButtonsView())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'✅ ✅ ✅ ログイン成功: {self.user.name} (V17 Final) ✅ ✅ ✅')

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            res = requests.get(GAS_URL, params={'type': 'fetch_rss'}, timeout=20)
            feed = feedparser.parse(res.text)
            if not feed.entries: return
            latest = feed.entries[0]
            if self.last_link == latest.link: return
            if any(k in latest.title for k in ['カードデザイン', '公開', '新カード']):
                ch = self.get_channel(ANNOUNCE_CH_ID)
                if ch: await ch.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
            self.last_link = latest.link
        except: pass

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            await after.channel.send(f"🎲 **自動割り振り**\n**{p1.display_name}** ⇒ **{roles[0]}**\n**{p2.display_name}** ⇒ **{roles[1]}**", silent=True, delete_after=60)

bot = MyBot()

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_all(ctx):
    await ctx.send(embed=discord.Embed(title="✅ 参加承認", color=discord.Color.green()), view=RulesOnlyView())
    await ctx.send(embed=discord.Embed(title="📝 TCG IDの登録", description="TCG IDを登録してください", color=discord.Color.blue()), view=RegistrationOnlyView())
    await ctx.send(embed=discord.Embed(title="🏆 ポイント確認", color=discord.Color.blue()), view=PointsOnlyView())

if __name__ == "__main__":
    Thread(target=run_flask).start()
    if not TOKEN:
        print("❌ 致命的エラー: DISCORD_TOKEN が設定されていません。")
        sys.exit(1)
    try:
        print("🚀 Discordへ接続を開始します...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ ログインに失敗しました: {e}")
