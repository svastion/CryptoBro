import discord
import os

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    channel = client.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("WhaleTracker бот активирован и готов к работе!")
    else:
        print("Канал не найден. Проверь ID.")

client.run(TOKEN)