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
ETHERSCAN_URL = "https://api.etherscan.io/api"

logging.basicConfig(level=logging.INFO)

async def fetch_tx_details(tx_hash: str) -> dict:
    try:
        url = f"{ETHERSCAN_URL}?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={ETHERSCAN_API_KEY}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            return resp.json().get("result", {})
    except Exception as e:
        logging.error(f"[Etherscan] Error fetching tx {tx_hash}: {e}")
        return {}

def format_log_message(tx: dict) -> str:
    return (
        f"**Tx Hash:** [{tx.get('hash')}](https://etherscan.io/tx/{tx.get('hash')})\n"
        f"**From:** `{tx.get('from')}`\n"
        f"**To:** `{tx.get('to')}`\n"
        f"**Value:** `{int(tx.get('value', '0x0'), 16) / 1e18:.6f} ETH`\n"
        f"**Nonce:** `{tx.get('nonce')}`\n"
        f"**Gas:** `{tx.get('gas')}`\n"
        "----------------------------"
    )

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:300]}...")

        block = payload.get("block", {})
        logs = block.get("logs", [])
        transactions = block.get("transactions", [])
        messages = []

        if logs:
            for log in logs:
                tx = log.get("transaction", {})
                msg = format_log_message(tx)
                messages.append(msg)
        elif transactions:
            for tx in transactions:
                tx_hash = tx.get("hash")
                if tx_hash:
                    data = await fetch_tx_details(tx_hash)
                    if data:
                        msg = format_log_message(data)
                        messages.append(msg)

        if not messages:
            messages.append(f"⚠️ No logs in block `{block.get('number', 'Unknown')}`. Full event: `{json.dumps(payload)[:200]}`")

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"[ERROR] Webhook failed: {e}")
        return {"status": "error", "detail": str(e)}