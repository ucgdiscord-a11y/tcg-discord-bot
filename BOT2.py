import discord
from discord.ext import commands, tasks
import random
import feedparser
import requests
import datetime
import os
from threading import Thread
from flask import Flask

TOKEN = os.getenv('DISCORD_TOKEN')
GAS_URL = os.getenv('GAS_URL')

ROLE_ID = 1478266543480766716        
ANNOUNCE_CH_ID = 1476095569595334718 
WELCOME_CH_ID = 1464168951012393021  
RSS_URL = 'https://nitter.perennialte.ch/ucg_jp/rss' 
KEYWORDS = ['カードデザイン', '公開', '新カード'] 

app = Flask('')
@app.route('/')
def home(): return "Bot is Alive!"
def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run)
    t.start()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = intents.members = intents.guilds = intents.voice_states = True
        super().__init__(command_prefix='/', intents=intents)
        self.active_messages = {}
        self.match_starts = {}

    async def on_ready(self):
        if not self.check_twitter.is_running(): self.check_twitter.start()
        print(f'Logged in as {self.user.name}')

    @tasks.loop(minutes=15)
    async def check_twitter(self):
        try:
            feed = feedparser.parse(RSS_URL)
            if feed.entries:
                latest = feed.entries[0]
                if any(k in latest.title for k in KEYWORDS):
                    channel = self.get_channel(ANNOUNCE_CH_ID)
                    if channel: await channel.send(f"📢 **Twitter速報**\n{latest.title}\n{latest.link}")
        except: pass

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None and len(after.channel.members) == 2:
            p1, p2 = after.channel.members[0], after.channel.members[1]
            roles = ["先攻", "後攻"]; random.shuffle(roles)
            msg = await after.channel.send(f"🎲 **割り振り**\n{p1.mention}⇒{roles[0]}\n{p2.mention}⇒{roles[1]}", silent=True)
            self.active_messages[after.channel.id] = msg
            self.match_starts[after.channel.id] = {"time": datetime.datetime.now(), "p1": p1.name, "p2": p2.name}
        elif before.channel is not None and len(before.channel.members) < 2:
            if before.channel.id in self.active_messages:
                try: await self.active_messages[before.channel.id].delete()
                except: pass
            if before.channel.id in self.match_starts:
                data = self.match_starts.pop(before.channel.id)
                duration_min = round((datetime.datetime.now() - data["time"]).total_seconds() / 60, 1)
                requests.post(GAS_URL, json={"type": "match_history", "p1_name": data["p1"], "p2_name": data["p2"], "duration": f"{duration_min}分", "channel": before.channel.name})

bot = MyBot()
if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
