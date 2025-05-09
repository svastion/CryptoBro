import os
import logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from datetime import datetime
import httpx

load_dotenv()

app = FastAPI()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
USD_THRESHOLD = 1  # минимум 1 доллар

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

@app.post("/")
async def handle_webhook(request: Request):
    try:
        payload = await request.json()

        logs = payload.get("block", {}).get("logs", [])
        if not logs:
            logger.info("[INFO] No logs in event")
            return {"status": "ignored"}

        for log in logs:
            tx = log.get("transaction", {})
            from_addr = tx.get("from", {}).get("address", "unknown")
            to_addr = tx.get("to", {}).get("address", "unknown")
            tx_hash = tx.get("hash", "unknown")
            raw_value = int(tx.get("value", "0"))
            value_eth = raw_value / 10**18
            direction = "IN" if to_addr else "OUT"
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

            if value_eth * 2000 < USD_THRESHOLD:  # Приблизительно, если нет API-подключения
                logger.info(f"[INFO] Skipped tx ~${value_eth*2000:.2f}")
                continue

            message = (
                f"**Whale Alert!**\n"
                f"**Amount:** ~${value_eth*2000:,.2f} (≈{value_eth:.4f} ETH)\n"
                f"**Direction:** `{direction}`\n"
                f"**From:** `{from_addr}`\n"
                f"**To:** `{to_addr}`\n"
                f"**TX Hash:** https://etherscan.io/tx/{tx_hash}\n"
                f"**Time:** {timestamp}"
            )

            async with httpx.AsyncClient() as client:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": message})

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error"}