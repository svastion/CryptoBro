import os
import logging
import requests
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
USD_THRESHOLD = float(os.getenv("USD_THRESHOLD", "10000"))

app = FastAPI()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    events = body if isinstance(body, list) else [body]

    for event in events:
        if not isinstance(event, dict):
            logger.error(f"[SKIPPED] Unexpected event type: {type(event)} — {event}")
            continue

        try:
            token_address = event.get("rawContract", {}).get("address")
            amount = float(event.get("value", 0))
            usd_value = float(event.get("valueUsd", 0))
            from_address = event.get("from")
            to_address = event.get("to")
            tx_hash = event.get("hash")
            direction = "IN" if event.get("to") else "OUT"

            if usd_value < USD_THRESHOLD:
                logger.info("[INFO] Skipped due to low USD value")
                continue

            message = (
                f"**Whale Alert!**
"
                f"**Amount:** `${usd_value:,.0f}`
"
                f"**Token:** `{token_address}`
"
                f"**Direction:** `{direction}`
"
                f"**From:** `{from_address}`
"
                f"**To:** `{to_address}`
"
                f"**TX Hash:** [View TX](https://etherscan.io/tx/{tx_hash})
"
                f"**Time:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            )

            data = {"content": message}
            response = requests.post(DISCORD_WEBHOOK_URL, json=data)
            response.raise_for_status()

        except Exception as e:
            logger.error(f"[ERROR] Failed to process event: {e}")

    return {"status": "ok"}
