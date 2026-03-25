import discord
from discord.ext import commands, tasks
import requests
import os
import sys
import feedparser
import datetime
import random
from threading import Thread
from flask import Flask

# =============================================================
# 【設定】パソコンで動かす場合は '' の中に直接入力してください
# Renderで動かす場合は、ここの書き換えは不要です（Environmentを使用）
# =============================================================
TOKEN = os.getenv('DISCORD_TOKEN', 'あなたのトークンをここに貼る')
GAS_URL = os.getenv('GAS_URL', 'あなたのGASのURLをここに貼る')

ROLE_ID = 1478266543480766716        # 参加承認ロールID
ANNOUNCE_CH_ID = 1476095569595334718 # 速報・誘導チャンネルID
# =============================================================

# --- Webサーバー (Render稼働維持用) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is Online!"
def run_flask():
    try:
        port = int(os.environ.get("PORT", 10000))
        app.run(host='0.0.0.0', port=port)
    except: pass

# --- UI View: 参加承認 ---
class RulesView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="✅ 同意して全機能を解放", style=discord.ButtonStyle.green, custom_id="v26_agree")
    async def agree(self, it: discord.Interaction, b):
        role = it.guild.get_role(ROLE_ID)
        try:
            await it.user.add_roles(role)
            await it.response.send_message("承認完了！全機能が解放されました。", ephemeral=True)
        except: await it.response.send_message("❌ 役職エラー：ボットの役職をメンバーより上に上げてください。", ephemeral=True)

# --- UI View: ID登録・ポイント管理 ---
class RegistrationView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="📝 TCG IDを登録する", style=discord.ButtonStyle.primary, custom_id="v26_reg")
    async def reg(self, it: discord.Interaction, b):
        modal = discord.ui.Modal(title='TCG IDの登録')
        tcg_input = discord.ui.TextInput(label='あなたのTCG ID', placeholder='例: 12345678', min_length=1)
        async def on_submit(it_m: discord.Interaction):
            await it_m.response.defer(ephemeral=True)
            payload = {"type": "register", "user_id": str(it_m.user.id), "user_name": it_m.user.display_name, "tcg_id": tcg_input.value}
            requests.post(GAS_URL, json=payload, timeout=10)
            await it_m.followup.send(f"✅ ID: `{tcg_input.value}` を登録完了！", ephemeral=True)
        modal.on_submit = on_submit
        modal.add_item(tcg_input)
        await it.response.send_modal(modal)

    @discord.ui.button(label="🏆 累計ポイントを確認する", style=discord.ButtonStyle.primary, custom_id="v26_pts")
    async def check(self, it: discord.Interaction, b):
        await it.response.defer(ephemeral=True)
        try:
            res = requests.get(GAS_URL, params={'type': 'get_points', 'user_id': str(it.user.id)}, timeout=10)
            await it.followup.send(f"🏆 現在の累計ポイントは **{res.text}pt** です！", ephemeral=True)
        except: await it.followup.send("⚠️ 取得失敗：GASのURL設定を確認してください。", ephemeral=True)

# --- UI View: 地域選択 ---
class RegionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.region_list = ["東北・北海道", "関東", "北信越", "中部", "関西", "四国・中国", "九州・沖縄"]
    
    async def update_region(self, it: discord.Interaction, name):
        # 現在の重複地域役職を削除
        to_rem = [discord.utils.get(it.guild.roles, name=r) for r in self.region_list if discord.utils.get(it.guild.roles, name=r) in it.user.roles]
        if to_rem: await it.user.remove_roles(*[r for r in to_rem if r])
        # 新しい地域役職を付与
        new = discord.utils.get(it.guild.roles, name=name)
        if new:
            await it.user.add_roles(new)
            await it.response.send_message(f"✅ 所属地域を「{name}」に設定しました！", ephemeral=True)
        else: await it.response.send_message(f"❌ 役職「{name}」がサーバー内に見つかりません。", ephemeral=True)

    @discord.ui.button(label="東北・北海道", style=discord.ButtonStyle.secondary, custom_id="r1")
    async def b1(self, it, b): await self.update_region(it, "東北・北海道")
    @discord.ui.button(label="関東", style=discord.ButtonStyle.secondary, custom_id="r2")
    async def b2(self, it, b): await self.update_region(it, "関東")
    @discord.ui.button(label="北信越", style=discord.ButtonStyle.secondary, custom_id="r3")
    async def b3(self, it, b): await self.update_region(it, "北信越")
    @discord.ui.button(label="中部", style=discord.ButtonStyle.secondary, custom_id="r4")
    async def b4(self, it, b): await self.update_region(it, "中部")
    @discord.ui.button(label="関西", style=discord.ButtonStyle.secondary, custom_id="r5")
    async def b5(self, it, b): await self.update_region(it, "関西")
    @discord.ui.button(label="四国・中国", style=discord.ButtonStyle.secondary, custom_id="r6", row=1)
    async def b6(self, it, b): await self.update_region(it, "四国・中国")
    @discord.ui.button(label="九州・沖縄", style=discord.ButtonStyle.secondary, custom_id="r7", row=1)
    async def b7(self, it, b): await self.update_region(it, "九州・沖縄")

# --- ボット本体 ---
class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.last_link = None
        self.match_starts = {}

    async def on_ready(self):
        # ボタンの永続化
        self.add_view(RulesView()); self.add_view(RegistrationView()); self.add_view(RegionView())
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'✅ ログイン成功: {self.user.name}\n!rules, !reg_panel, !points, !regions で個別設置可能です。')

    # Twitter速報
    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            res = requests.get(GAS_URL, params={'type': 'fetch_rss'}, timeout=20)
            feed = feedparser.parse(res.text)
            if not feed.entries: return
            latest = feed.entries[0]
            if self.last_link != latest.link:
                if any(k in latest.title for k in ['カードデザイン', '公開', '新カード', '発表']):
                    ch = self.get_channel(ANNOUNCE_CH_ID)
                    if ch: await ch.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
                self.last_link = latest.link
        except: pass

    # VC対戦管理
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            self.match_starts[after.channel.id] = {"time": datetime.datetime.now(), "p1_id": p1.id, "p2_id": p2.id, "p1_name": p1.name, "p2_name": p2.name}
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            await after.channel.send(f"🎲 **自動割り振り**\n**{p1.display_name}** ⇒ **{roles[0]}**\n**{p2.display_name}** ⇒ **{roles[1]}**", delete_after=60)
        elif before.channel is not None and len(before.channel.members) < 2:
            if before.channel.id in self.match_starts:
                d = self.match_starts.pop(before.channel.id)
                dur = round((datetime.datetime.now() - d["time"]).total_seconds() / 60, 1)
                requests.post(GAS_URL, json={"type": "match_pending", "p1_id": str(d["p1_id"]), "p1_name": d["p1_name"], "p2_id": str(d["p2_id"]), "p2_name": d["p2_name"], "duration": f"{dur}分", "channel": before.channel.name})

bot = MyBot()

# --- 個別呼び出しコマンド ---
@bot.command()
@commands.has_permissions(administrator=True)
async def rules(ctx): await ctx.send(embed=discord.Embed(title="✅ 参加承認", description="規約に同意する場合はボタンを押してください。", color=discord.Color.green()), view=RulesView())

@bot.command()
@commands.has_permissions(administrator=True)
async def reg_panel(ctx): await ctx.send(embed=discord.Embed(title="📝 TCG ID登録", description="IDの登録はこちらから行えます。", color=discord.Color.blue()), view=RegistrationView())

@bot.command()
@commands.has_permissions(administrator=True)
async def points(ctx): await ctx.send(embed=discord.Embed(title="🏆 ポイント確認", description="現在の累計ポイントを表示します。", color=discord.Color.gold()), view=RegistrationView())

@bot.command()
@commands.has_permissions(administrator=True)
async def regions(ctx): await ctx.send(embed=discord.Embed(title="📍 地域選択", description="あなたの所属地域を選択してください。", color=discord.Color.magenta()), view=RegionView())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_all(ctx):
    await rules(ctx); await reg_panel(ctx); await regions(ctx)
    await ctx.send("✅ すべての管理パネルを設置しました。")

if __name__ == "__main__":
    Thread(target=run_flask).start()
    if TOKEN and TOKEN != 'あなたのトークンをここに貼る':
        bot.run(TOKEN)
    else: print("❌ TOKENが設定されていません。")
