import os
import json
import logging
import httpx
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

logging.basicConfig(level=logging.INFO)

# Получение цены токена в USDT через CoinGecko
async def get_token_price_usdt(token_address):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.coingecko.com/api/v3/simple/token_price/ethereum",
                params={"contract_addresses": token_address, "vs_currencies": "usd"},
                timeout=10
            )
            data = response.json()
            price = data.get(token_address.lower(), {}).get("usd", None)
            return price
    except Exception as e:
        logging.error(f"Price fetch error: {e}")
        return None

def is_zero_value(value):
    try:
        return int(value, 16) == 0
    except:
        return True

def truncate_address(addr):
    return f"{addr[:6]}...{addr[-4:]}" if addr else "Unknown"

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:300]}...")

        block = payload.get("data", {}).get("block", {})
        block_number = block.get("number", "N/A")
        logs = block.get("logs", [])

        if not logs:
            logging.info("No logs in block")
            return {"status": "no_logs"}

        for log in logs:
            tx = log.get("transaction", {})
            from_addr = tx.get("from", {}).get("address", "Unknown")
            to_addr = tx.get("to", {}).get("address", "Unknown")
            tx_hash = tx.get("hash", "")
            value_hex = tx.get("value", "0x0")

            if is_zero_value(value_hex):
                continue

            topics = log.get("topics", [])
            token_transfer = topics and topics[0].startswith("0xddf252ad")
            token_address = log.get("account", {}).get("address", None)

            value_eth = int(value_hex, 16) / 1e18
            price_usdt = None
            if token_address:
                price_usdt = await get_token_price_usdt(token_address)
            usdt_display = f"{value_eth * price_usdt:.2f} USDT" if price_usdt else "N/A"

            content = {
                "embeds": [
                    {
                        "title": "🚨 New Transaction",
                        "description": f"**Block:** `{block_number}`\n"
                                       f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\n"
                                       f"**From:** `{truncate_address(from_addr)}`\n"
                                       f"**To:** `{truncate_address(to_addr)}`\n"
                                       f"**ETH Value:** `{value_eth:.6f}` ETH\n"
                                       f"**USDT Value:** `{usdt_display}`\n"
                                       f"**Type:** {'Token Transfer' if token_transfer else 'Native ETH'}",
                        "color": 0x3498db
                    }
                ]
            }

            async with httpx.AsyncClient() as client:
                await client.post(DISCORD_WEBHOOK_URL, json=content)

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"[ERROR] Failed to process webhook: {e}")
        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK_URL, json={"content": f"❗ Error parsing transaction: {e}"})
        return {"status": "error", "details": str(e)}