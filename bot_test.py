from fastapi import FastAPI, Request
import requests
import discord
import asyncio
import os

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(client.start(DISCORD_TOKEN))

@app.post("/webhook")
async def receive_tx(request: Request):
    data = await request.json()
    
    tx = data.get("event", {}).get("transaction", {})
    wallet = tx.get("to")
    value = int(tx.get("value", 0)) / 10**18
    tx_hash = tx.get("hash")

    channel = client.get_channel(DISCORD_CHANNEL_ID)
    if channel:
        await channel.send(
            f"**Whale Alert!**\n"
            f"To: `{wallet}`\n"
            f"Amount: `{value} ETH`\n"
            f"[TX Link](https://etherscan.io/tx/{tx_hash})"
        )

    return {"status": "ok"}