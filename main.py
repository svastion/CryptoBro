from fastapi import FastAPI, Request
import requests
import os
from datetime import datetime
from decimal import Decimal
import logging

app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
MIN_USD_THRESHOLD = 10000  # фильтр на сумму в USD

# Логгирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def format_discord_message(token, amount, usd_value, from_address, to_address, tx_hash, direction, timestamp):
    etherscan_base = "https://etherscan.io"
    return (
        "**Whale Alert!**\n"
        f"**Token**: `{token}`\n"
        f"**Amount**: `{amount:,.2f}`\n"
        f"**Value**: `${usd_value:,.2f}`\n"
        f"**Direction**: `{direction}`\n"
        f"**From**: [`{from_address[:6]}...{from_address[-4:]}`]({etherscan_base}/address/{from_address})\n"
        f"**To**: [`{to_address[:6]}...{to_address[-4:]}`]({etherscan_base}/address/{to_address})\n"
        f"**TX Hash**: [View TX]({etherscan_base}/tx/{tx_hash})\n"
        f"**Time**: `{timestamp}` UTC"
    )


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    for event in data.get("event", {}).get("activity", []):
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