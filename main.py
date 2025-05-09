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
        block = event['block']
        block_number = block.get('number', 'Unknown')
        block_hash = block.get('hash', 'Unknown')
        timestamp = block.get('timestamp', 'Unknown')
        logs = block.get('logs', [])

        if not logs:
            return ["No transaction logs in this block."]

        messages = []

        for log in logs:
            tx = log.get("transaction", {})
            from_address = tx.get("from", {}).get("address", "N/A")
            to_address = tx.get("to", {}).get("address", "N/A")
            tx_hash = tx.get("hash", "N/A")
            value_hex = tx.get("value", "0x0")
            topics = log.get("topics", [])
            is_token_transfer = topics and topics[0].lower().startswith("0xddf252ad")

            try:
                value_eth = int(value_hex, 16) / 1e18
            except Exception:
                value_eth = 0

            msg = f"**New Transaction**
"
            msg += f"Block: `{block_number}` | Hash: [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})
"
            msg += f"From: `{from_address}`
To: `{to_address}`
"
            msg += f"Value: `{value_eth:.6f} ETH`
"
            if is_token_transfer:
                msg += f"**Token Transfer Detected**
"
            msg += f"Timestamp: `{timestamp}`
"
            msg += "---------------------------"

            messages.append(msg)

        return messages if messages else ["No valid transactions in this block."]

    except Exception as e:
        logging.error(f"Error formatting message: {e}")
        return ["Error parsing transaction."]

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:500]}...")

        messages = format_transaction_message(payload.get("data", {}))

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error", "details": str(e)}
