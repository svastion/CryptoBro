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
        block_number = event['block']['number']
        block_hash = event['block']['hash']
        timestamp = event['block']['timestamp']

        logs = event['block'].get('logs', [])
        messages = []

        for log in logs:
            tx = log.get("transaction", {})
            from_address = tx.get("from", {}).get("address", "Unknown")
            to_address = tx.get("to", {}).get("address", "Unknown")
            tx_hash = tx.get("hash", "Unknown")
            value = tx.get("value", "0")
            topics = log.get("topics", [])
            token_transfer = len(topics) > 0 and topics[0].startswith("0xddf252ad")

            message = f"**New Transaction Detected**\n"
            message += f"Block: `{block_number}`\n"
            message += f"Tx Hash: [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\n"
            message += f"From: `{from_address}`\n"
            message += f"To: `{to_address}`\n"
            message += f"Value: `{int(value, 16) / 1e18:.4f} ETH`\n"
            if token_transfer:
                message += f"Detected as **Token Transfer**\n"
            message += f"---------------------------"

            messages.append(message)

        return messages

    except Exception as e:
        logging.error(f"Error formatting message: {e}")
        return ["Error parsing transaction."]

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
        logging.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error", "details": str(e)}
