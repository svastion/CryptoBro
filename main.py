import os
import requests
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from decimal import Decimal
from datetime import datetime

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MIN_USD_THRESHOLD = Decimal(os.getenv("MIN_USD_THRESHOLD", "10000"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI()

def format_discord_message(token, amount, usd_value, from_address, to_address, tx_hash, direction, timestamp):
    return f"""**Whale Alert!**
**Token:** `{token}`
**Amount:** `{amount}`
**USD Value:** `${usd_value:,.0f}`
**Direction:** `{direction}`
**From:** `{from_address}`
**To:** `{to_address}`
**TX Hash:** [View on Etherscan](https://etherscan.io/tx/{tx_hash})
**Time:** {timestamp}"""

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    events = data.get("event", {}).get("activity", [])
    if not isinstance(events, list):
        logger.error("[ERROR] Invalid event payload format")
        return {"status": "invalid"}

    for event in events:
        if not isinstance(event, dict):
            logger.warning(f"[WARNING] Skipped non-dict event: {event}")
            continue

        try:
            usd_value = Decimal(event.get("value", {}).get("value", 0))
            if usd_value < MIN_USD_THRESHOLD:
                logger.info("[INFO] Skipped due to low USD value")
                continue

            token = event.get("asset", {}).get("contractAddress", "Unknown")
            amount = Decimal(event.get("value", {}).get("amount", 0))
            from_address = event.get("fromAddress", "None")
            to_address = event.get("toAddress", "None")
            tx_hash = event.get("hash", "None")
            direction = event.get("category", "None")
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            logger.debug(f"[DEBUG] Token: {token}, Amount: {amount}, USD: {usd_value}")

            message = format_discord_message(
                token=token,
                amount=amount,
                usd_value=usd_value,
                from_address=from_address,
                to_address=to_address,
                tx_hash=tx_hash,
                direction=direction,
                timestamp=timestamp,
            )

            response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
            if response.status_code != 204:
                logger.warning(f"[WARNING] Discord responded with status {response.status_code}: {response.text}")

        except Exception as e:
            logger.error(f"[ERROR] Failed to process event: {e}")

    return {"status": "ok"}