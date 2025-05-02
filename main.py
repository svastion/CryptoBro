import os
import logging
from fastapi import FastAPI, Request
import httpx
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = FastAPI()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
USD_THRESHOLD = 10000  # Порог в USD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()
        for event in payload.get("event", []):
            if not isinstance(event, dict):
                logger.error("[ERROR] Failed to process event: not a dict")
                continue

            token_address = event.get("rawContract", {}).get("address")
            from_address = event.get("from")
            to_address = event.get("to")
            direction = "IN" if to_address else "OUT"
            tx_hash = event.get("hash")
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            amount_token = int(event.get("value", 0)) / (10 ** event.get("rawContract", {}).get("decimals", 18))
            usd_value = float(event.get("valueUSD", 0))

            if usd_value < USD_THRESHOLD:
                logger.info(f"[INFO] Skipped due to low USD value: ${usd_value}")
                continue

            logger.info(f"[DEBUG] Whale TX found: ${usd_value} | Token: {token_address}")

            message = f"""**Whale Alert!**
Amount: ${usd_value:,.0f}
Token: `{token_address}`
Direction: `{direction}`
From: `{from_address}`
To: `{to_address}`
TX Hash: https://etherscan.io/tx/{tx_hash}
Time: {timestamp}
"""

            async with httpx.AsyncClient() as client:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": message})

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error"}