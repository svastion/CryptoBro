import os
import json
import logging
import httpx
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
COINGECKO_API = "https://api.coingecko.com/api/v3/simple/token_price/ethereum"

logging.basicConfig(level=logging.INFO)

async def get_token_price_usd(token_address):
    try:
        url = f"{COINGECKO_API}?contract_addresses={token_address}&vs_currencies=usd"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json()
            return data.get(token_address.lower(), {}).get("usd", 0)
    except Exception as e:
        logging.error(f"Failed to get token price: {e}")
        return 0

async def get_token_info(token_address):
    try:
        url = f"https://api.etherscan.io/api?module=token&action=tokeninfo&contractaddress={token_address}&apikey={ETHERSCAN_API_KEY}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            result = response.json().get("result", [{}])[0]
            return {
                "name": result.get("tokenName", "Unknown"),
                "symbol": result.get("symbol", "???"),
                "decimals": int(result.get("decimals", 18))
            }
    except Exception as e:
        logging.error(f"Failed to get token info: {e}")
        return {"name": "Unknown", "symbol": "???", "decimals": 18}

def parse_address(topic_hex):
    return f"0x{topic_hex[-40:]}"

def wei_to_eth(value_hex):
    try:
        return int(value_hex, 16) / 1e18
    except:
        return 0

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:300]}...")
        logs = payload.get("event", {}).get("data", {}).get("block", {}).get("logs", [])
        block_number = payload["event"]["data"]["block"]["number"]
        block_hash = payload["event"]["data"]["block"]["hash"]

        if not logs:
            await send_to_discord("⚠️ No transaction logs in this block.")
            return {"status": "ok"}

        for log in logs:
            topics = log.get("topics", [])
            if not topics or not topics[0].startswith("0xddf252ad"):
                continue  # Not a token transfer

            token_address = log.get("address")
            tx = log.get("transaction", {})
            from_address = parse_address(topics[1]) if len(topics) > 1 else "N/A"
            to_address = parse_address(topics[2]) if len(topics) > 2 else "N/A"
            tx_hash = tx.get("hash", "N/A")
            value_raw = int(log.get("data", "0x0"), 16)
            if value_raw == 0:
                continue

            token_info = await get_token_info(token_address)
            decimals = token_info["decimals"]
            value = value_raw / (10 ** decimals)
            price = await get_token_price_usd(token_address)
            usd_value = value * price

            msg = (
                f"🚨 **New Transaction**\n"
                f"Block: `{block_number}`\n"
                f"Tx Hash: [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\n"
                f"From: `{from_address}`\n"
                f"To: `{to_address}`\n"
                f"Token: `{token_info['symbol']}`\n"
                f"Amount: `{value:.4f}` {token_info['symbol']}\n"
                f"Value: `${usd_value:,.2f}`\n"
                f"Type: 🪙 Token Transfer\n"
                f"-------------------------"
            )
            await send_to_discord(msg)

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        await send_to_discord("❗ Error parsing transaction.")
        return {"status": "error", "details": str(e)}

async def send_to_discord(message: str):
    async with httpx.AsyncClient() as client:
        await client.post(DISCORD_WEBHOOK_URL, json={"content": message})