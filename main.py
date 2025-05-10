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

def format_transaction_message(event):
    try:
        block = event.get("block", {})
        block_number = block.get("number")
        block_hash = block.get("hash")
        timestamp = block.get("timestamp")

        logs = block.get("logs", [])
        messages = []

        for log in logs:
            tx = log.get("transaction", {})
            value_hex = tx.get("value", "0x0")
            value_eth = int(value_hex, 16) / 1e18

            if value_eth == 0:
                continue

            from_address = tx.get("from", {}).get("address", "Unknown")
            to_address = tx.get("to", {}).get("address", "Unknown")
            tx_hash = tx.get("hash", "Unknown")
            topics = log.get("topics", [])
            token_transfer = any(t.startswith("0xddf252ad") for t in topics)

            message = f"ð¨ **New Transaction**
"
            message += f"**Block:** `{block_number}`
"
            message += f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})
"
            message += f"**From:** `{from_address}`
"
            message += f"**To:** `{to_address}`
"
            message += f"**Value:** `{value_eth:.6f} ETH`
"
            if token_transfer:
                message += f"**Type:** ðª Token Transfer
"
            message += "---------------------------"

            messages.append(message)

        return messages if messages else ["No transaction logs in this block."]

    except Exception as e:
        logging.error(f"Error formatting message: {e}")
        return ["âError parsing transaction."]

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:300]}...")
        messages = format_transaction_message(payload)

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"Webhook Error: {e}")
        return {"status": "error", "details": str(e)}