import os
import logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from datetime import datetime
import httpx

load_dotenv()

app = FastAPI()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
USD_THRESHOLD = 10000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        data = await request.json()

        events = data.get("event", [])
        if not isinstance(events, list):
            logger.error("[ERROR] Payload 'event' is not a list")
            return {"status": "ignored"}

        for evt in events:
            if not isinstance(evt, dict):
                logger.error("[ERROR] Event is not a dict")
                continue

            try:
                token_address = evt.get("rawContract", {}).get("address", "unknown")
                from_addr = evt.get("from", "unknown")
                to_addr = evt.get("to", "unknown")
                tx_hash = evt.get("hash", "unknown")
                value_usd = float(evt.get("valueUSD", 0))
                raw_value = int(evt.get("value", 0))
                decimals = int(evt.get("rawContract", {}).get("decimals", 18))
                amount_tokens = raw_value / (10 ** decimals)
                direction = "IN" if to_addr else "OUT"
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

                if value_usd < USD_THRESHOLD:
                    logger.info(f"[INFO] Skipped tx ${value_usd}")
                    continue

                message = (
                    f"**Whale Alert!**\n"
                    f"**Amount:** ${value_usd:,.0f}\n"
                    f"**Token:** `{token_address}`\n"
                    f"**Direction:** `{direction}`\n"
                    f"**From:** `{from_addr}`\n"
                    f"**To:** `{to_addr}`\n"
                    f"**Quantity:** `{amount_tokens:.4f}` tokens\n"
                    f"**TX Hash:** https://etherscan.io/tx/{tx_hash}\n"
                    f"**Time:** {timestamp}"
                )

                async with httpx.AsyncClient() as client:
                    await client.post(DISCORD_WEBHOOK_URL, json={"content": message})

            except Exception as inner:
                logger.error(f"[ERROR] Problem in event parsing: {inner}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error"}