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

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:300]}...")

        block = payload.get("data", {}).get("block", {})
        logs = block.get("logs", [])

        if not logs:
            logging.info("No logs in block")
            return {"status": "no_logs"}

        messages = []

        for log in logs:
            try:
                tx = log.get("transaction", {})
                from_address = tx.get("from", {}).get("address", "Unknown")
                to_address = tx.get("to", {}).get("address", "Unknown")
                tx_hash = tx.get("hash", "Unknown")
                value = tx.get("value", "0x0")
                eth_value = int(value, 16) / 1e18 if value else 0

                if eth_value == 0:
                    continue

                topics = log.get("topics", [])
                token_transfer = any(t.startswith("0xddf252ad") for t in topics)

                msg = f"🔔 **New Transaction**\\n"
                msg += f"**Block:** `{block.get('number')}`\\n"
                msg += f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})\\n"
                msg += f"**From:** `{from_address}`\\n"
                msg += f"**To:** `{to_address}`\\n"
                msg += f"**Value:** `{eth_value:.6f} ETH`\\n"
                if token_transfer:
                    msg += f"**Type:** 🪙 *Token Transfer*\\n"
                msg += f"---------------------------"

                messages.append(msg)
            except Exception as e:
                logging.error(f"Webhook Error: {e}")
                messages.append("❗ Error parsing transaction.")

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error", "details": str(e)}