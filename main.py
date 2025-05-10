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
            logging.info(f"Etherscan response for {tx_hash}: {response.text[:300]}")
            data = response.json().get("result", {})
            return data
    except Exception as e:
        logging.error(f"[ERROR] Etherscan API failed for {tx_hash}: {e}")
        return {}

def format_tx_message(tx_data):
    tx_hash = tx_data.get("hash", "Unknown")
    from_addr = tx_data.get("from", "Unknown")
    to_addr = tx_data.get("to", "Unknown")
    gas = tx_data.get("gas", "Unknown")
    nonce = tx_data.get("nonce", "Unknown")
    input_data = tx_data.get("input", "0x")[:10] + "..."

    message = (
        f"**Etherscan TX Insight**
"
        f"**Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})
"
        f"**From:** `{from_addr}`
"
        f"**To:** `{to_addr}`
"
        f"**Gas:** `{gas}` | **Nonce:** `{nonce}`
"
        f"**Method:** `{input_data}`
"
        "----------------------------"
    )
    return message

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:500]}...")

        messages = []
        block = payload.get("block", {})
        logs = block.get("logs", [])
        transactions = block.get("transactions", [])

        if logs:
            messages.append(f"ð§© Logs found in block `{block.get('number', 'N/A')}`")
        elif transactions:
            for tx in transactions:
                tx_hash = tx.get("hash")
                if tx_hash:
                    details = await fetch_tx_details_from_etherscan(tx_hash)
                    msg = format_tx_message(details)
                    messages.append(msg)
        else:
            messages.append(f"ð§© No logs in block `{block.get('number', 'Unknown')}`. Full event: `{json.dumps(payload)[:200]}...`")

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"[ERROR] Webhook processing failed: {e}")
        return {"status": "error", "details": str(e)}