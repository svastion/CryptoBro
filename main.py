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
ETHERSCAN_API_URL = "https://api.etherscan.io/api"

logging.basicConfig(level=logging.INFO)


async def fetch_tx_details(tx_hash: str):
    try:
        url = (
            f"{ETHERSCAN_API_URL}?module=proxy"
            f"&action=eth_getTransactionByHash&txhash={tx_hash}"
            f"&apikey={ETHERSCAN_API_KEY}"
        )
        async with httpx.AsyncClient() as client:
            res = await client.get(url)
            if res.status_code == 200:
                return res.json().get("result", {})
            else:
                logging.error(f"[ERROR] Etherscan failed for tx {tx_hash}: {res.status_code}")
    except Exception as e:
        logging.error(f"[ERROR] Exception fetching Etherscan tx details: {e}")
    return {}


def build_log_messages(event: dict) -> list:
    block = event.get("block", {})
    logs = block.get("logs", [])
    block_number = block.get("number", "Unknown")
    timestamp = block.get("timestamp", "Unknown")

    messages = []
    if not logs:
        messages.append(f"⚠️ No logs in block `{block_number}`. Full event:\n```json\n{json.dumps(event, indent=2)[:1900]}```")
    else:
        for log in logs:
            tx = log.get("transaction", {})
            from_addr = tx.get("from", {}).get("address", "Unknown")
            to_addr = tx.get("to", {}).get("address", "Unknown")
            value = tx.get("value", "0x0")
            tx_hash = tx.get("hash", "Unknown")

            eth_val = int(value, 16) / 1e18 if value else 0
            msg = (
                f"🚨 **New On-chain Log**\n"
                f"**Block:** `{block_number}`\n"
                f"**From:** `{from_addr}`\n"
                f"**To:** `{to_addr}`\n"
                f"**ETH Value:** `{eth_val:.6f}`\n"
                f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\n"
                "----------------------------"
            )
            messages.append(msg)
    return messages


async def fetch_transactions_and_build_messages(payload: dict) -> list:
    block = payload.get("block", {})
    transactions = block.get("transactions", [])
    block_number = block.get("number", "Unknown")
    timestamp = block.get("timestamp", "Unknown")
    messages = []

    if not transactions:
        messages.append(f"❌ No transactions found in block `{block_number}`.")
        return messages

    for tx in transactions:
        tx_hash = tx.get("hash")
        if tx_hash:
            details = await fetch_tx_details(tx_hash)
            msg = (
                f"🔎 **Tx via Etherscan API**\n"
                f"**Block:** `{block_number}`\n"
                f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\n"
                f"**From:** `{details.get('from', 'N/A')}`\n"
                f"**To:** `{details.get('to', 'N/A')}`\n"
                f"**Gas:** `{details.get('gas', 'N/A')}`\n"
                f"**Nonce:** `{details.get('nonce', 'N/A')}`\n"
                f"**Method (Input):** `{details.get('input', '')[:10]}`\n"
                "----------------------------"
            )
            messages.append(msg)
    return messages


@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:300]}...")

        block = payload.get("block", {})
        logs = block.get("logs", [])

        if logs:
            messages = build_log_messages(payload)
        else:
            messages = await fetch_transactions_and_build_messages(payload)

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"[ERROR] Webhook processing failed: {e}")
        return {"status": "error", "details": str(e)}