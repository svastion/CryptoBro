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

def safe_get(d: dict, path: list, default="N/A"):
    for key in path:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return default
    return d

def format_transaction_message(event):
    try:
        block = event.get("block", {})
        block_number = block.get("number", "N/A")
        block_hash = block.get("hash", "N/A")
        timestamp = block.get("timestamp", "N/A")
        logs = block.get("logs", [])

        if not logs:
            return ["⚠️ **No transaction logs in this block.**"]

        messages = []

        for log in logs:
            tx = log.get("transaction", {})
            from_address = safe_get(tx, ["from", "address"])
            to_address = safe_get(tx, ["to", "address"])
            tx_hash = tx.get("hash", "N/A")
            value_hex = tx.get("value", "0x0")

            try:
                value_eth = int(value_hex, 16) / 1e18
            except:
                value_eth = 0.0

            topics = log.get("topics", [])
            is_token = topics and topics[0].lower().startswith("0xddf252ad")

            # Пропускать нулевые токены и ETH
            if value_eth == 0 and not is_token:
                continue

            msg = (
                f"**🚨 New Transaction**\n"
                f"> **Block:** `{block_number}`\n"
                f"> **Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\n"
                f"> **From:** `{from_address}`\n"
                f"> **To:** `{to_address}`\n"
                f"> **Value:** `{value_eth:.6f} ETH`\n"
            )

            if is_token:
                msg += f"> **Type:** 🪙 *Token Transfer*\n"

            msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━"

            messages.append(msg)

        return messages or ["⚠️ **No non-zero transactions detected.**"]

    except Exception as e:
        logging.error(f"[FATAL] Formatting error: {e}")
        return ["❌ Error parsing transaction."]

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:500]}...")

        messages = format_transaction_message(payload.get("event", {}).get("data", {}))

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"[ERROR] Webhook failed: {e}")
        return {"status": "error", "details": str(e)}