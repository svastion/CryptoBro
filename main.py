from fastapi import FastAPI, Request
import requests
import discord
import asyncio
import os
from datetime import datetime

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

intents = discord.Intents.default()
client = discord.Client(intents=intents)

app = FastAPI()

# Получить цену токена по контракту через CoinGecko (пример)
def get_token_price_usd(contract_address):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={contract_address}&vs_currencies=usd"
        response = requests.get(url)
        data = response.json()
        return data.get(contract_address.lower(), {}).get("usd", None)
    except:
        return None

# Получить ENS (если есть)
def resolve_ens(address):
    return address  # Можно подключить реальный ENS резолвер через Alchemy или Etherscan

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(client.start(DISCORD_TOKEN))

@app.post("/webhook")
async def receive_webhook(request: Request):
    data = await request.json()
    logs = data.get("event", {}).get("rawLogs", [])
    tx_hash = data.get("event", {}).get("transactionHash", "Unknown")
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    for log in logs:
        topics = log.get("topics", [])
        if len(topics) != 3:
            continue
        if topics[0].lower() != "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef":
            continue  # Не Transfer

        contract = log.get("address")
        from_address = "0x" + topics[1][-40:]
        to_address = "0x" + topics[2][-40:]
        value_hex = log.get("data", "0x0")
        try:
            value_int = int(value_hex, 16)
        except:
            continue

        # Получаем цену токена в $
        price = get_token_price_usd(contract)
        if price is None:
            continue

        # Пример: предполагаем 18 decimals (можно динамически получать через ABI)
        amount = value_int / (10 ** 18)
        amount_usd = amount * price

        # Фильтр: только если больше $10,000
        if amount_usd < 10000:
            continue

        direction = "OUT" if from_address.lower() in data.get("event", {}).get("involvedAddresses", []) else "IN"

        # ENS можно заменить, если настроен резолвер
        from_resolved = resolve_ens(from_address)
        to_resolved = resolve_ens(to_address)

        message = (
            f"**Whale Alert!**\n"
            f"**Amount:** ${amount_usd:,.0f}\n"
            f"**Token:** {contract}\n"
            f"**Direction:** {direction}\n"
            f"**From:** {from_resolved}\n"
            f"**To:** {to_resolved}\n"
            f"**TX Hash:** [{tx_hash}](https://etherscan.io/tx/{tx_hash})\n"
            f"**Time:** {timestamp}"
        )

        channel = client.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            await channel.send(message)

    return {"status": "ok"}