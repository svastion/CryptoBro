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
ETHERSCAN_API_URL = os.getenv("ETHERSCAN_API_URL", "https://api.etherscan.io/api")

logging.basicConfig(level=logging.INFO)

async def fetch_tx_details_from_etherscan(tx_hash):
    try:
        url = f"{ETHERSCAN_API_URL}?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={ETHERSCAN_API_KEY}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json().get("result", {})
            return data
    except Exception as e:
        logging.error(f"[ERROR] Etherscan API failed: {e}")
        return {}

def format_tx_message(tx_data):
    try:
        from_address = tx_data.get("from", "N/A")
        to_address = tx_data.get("to", "N/A")
        gas = tx_data.get("gas", "N/A")
        value = int(tx_data.get("value", "0x0"), 16) / 1e18 if tx_data.get("value") else 0
        nonce = tx_data.get("nonce", "N/A")
        tx_hash = tx_data.get("hash", "N/A")
        input_data = tx_data.get("input", "N/A")

        message = (
            f"**Etherscan Transaction**
"
            f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})
"
            f"**From:** `{from_address}`
"
            f"**To:** `{to_address}`
"
            f"**Value:** `{value:.6f} ETH`
"
            f"**Gas:** `{gas}`
"
            f"**Nonce:** `{nonce}`
"
            f"**Input:** `{input_data[:12]}...`
"
            f"----------------------------"
        )
        return message
    except Exception as e:
        logging.error(f"[ERROR] Formatting TX message: {e}")
        return "Error formatting transaction message."

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:500]}...")

        block = payload.get("block", {})
        logs = block.get("logs", [])
        messages = []

        if logs:
            for log in logs:
                tx = log.get("transaction", {})
                if tx and "hash" in tx:
                    etherscan_data = await fetch_tx_details_from_etherscan(tx["hash"])
                    msg = format_tx_message(etherscan_data)
                    messages.append(msg)
        else:
            transactions = block.get("transactions", [])
            for tx in transactions:
                if tx and "hash" in tx:
                    etherscan_data = await fetch_tx_details_from_etherscan(tx["hash"])
                    msg = format_tx_message(etherscan_data)
                    messages.append(msg)

        if not messages:
            messages.append("â No valid logs or transactions found in this block.")

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"[ERROR] Webhook failed: {e}")
        return {"status": "error", "details": str(e)}