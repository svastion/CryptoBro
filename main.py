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
        block_data = event.get("block", {})
        block_number = block_data.get("number", "Unknown")
        block_hash = block_data.get("hash", "Unknown")
        timestamp = block_data.get("timestamp", "Unknown")

        logs = block_data.get("logs", [])
        messages = []

        for log in logs:
            tx = log.get("transaction", {})
            from_address = tx.get("from", {}).get("address", "Unknown")
            to_address = tx.get("to", {}).get("address", "Unknown")
            tx_hash = tx.get("hash", "Unknown")
            value_hex = tx.get("value", "0x0")
            topics = log.get("topics", [])
            token_transfer = len(topics) > 0 and topics[0].startswith("0xddf252ad")

            value_eth = int(value_hex, 16) / 1e18
            if value_eth == 0:
                continue  # исключаем нулевые транзакции

            message = (
                f"🚨 **New Transaction**\n"
                f"**Block:** `{block_number}`\n"
                f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\n"
                f"**From:** `{from_address}`\n"
                f"**To:** `{to_address}`\n"
                f"**Value:** `{value_eth:.6f} ETH`\n"
            )

            if token_transfer:
                message += "**Type:** 🪙 Token Transfer\n"
            message += "----------------------------"

            messages.append(message)

        return messages if messages else ["No transaction logs in this block."]
    except Exception as e:
        logging.error(f"[ERROR] Formatting message failed: {e}")
        return [f"❗ Error parsing transaction."]

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:500]}...")
        messages = format_transaction_message(payload)

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})
        return {"status": "ok"}

    except Exception as e:
        logging.error(f"[ERROR] Webhook processing failed: {e}")
        return {"status": "error", "details": str(e)}