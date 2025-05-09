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
        block_number = block.get("number", "N/A")
        block_hash = block.get("hash", "N/A")
        timestamp = block.get("timestamp", "N/A")

        logs = block.get("logs", [])
        messages = []

        for log in logs:
            tx = log.get("transaction", {})
            tx_hash = tx.get("hash", "Unknown")
            from_address = tx.get("from", {}).get("address", "Unknown")
            to_address = tx.get("to", {}).get("address", "Unknown")
            value_hex = tx.get("value", "0x0")
            value_eth = int(value_hex, 16) / 1e18 if value_hex else 0

            topics = log.get("topics", [])
            token_transfer = topics and topics[0].lower().startswith("0xddf252ad")

            message = f"**New Transaction Event**\n"
            message += f"Block: `{block_number}` | Time: `{timestamp}`\n"
            message += f"[Tx Hash](https://etherscan.io/tx/{tx_hash})\n"
            message += f"From: `{from_address}`\nTo: `{to_address}`\n"
            message += f"ETH Value: `{value_eth:.6f}`\n"

            if token_transfer:
                token_from = topics[1][-40:] if len(topics) > 1 else "???"
                token_to = topics[2][-40:] if len(topics) > 2 else "???"
                message += f"**Token Transfer Detected**\n"
                message += f"From Token: `0x{token_from}`\nTo Token: `0x{token_to}`\n"

            message += f"────────────────────"
            messages.append(message)

        return messages or ["No transaction logs in this block."]

    except Exception as e:
        logging.exception("Error formatting message")
        return [f"Error parsing transaction: {e}"]

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
        logging.exception("Webhook handler failed")
        return {"status": "error", "details": str(e)}