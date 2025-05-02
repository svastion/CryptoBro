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
        event = data.get("event", {})
        raw_logs = event.get("rawLogs", [])
        tx_hash = event.get("transactionHash", "unknown")

        if not raw_logs:
            logger.info("[INFO] No logs in event")
            return {"status": "ignored"}

        log = raw_logs[0]
        token_address = log.get("address", "unknown")
        topics = log.get("topics", [])
        data_hex = log.get("data", "0x0")

        if len(topics) < 3:
            logger.warning("[WARN] Not enough topics in log")
            return {"status": "ignored"}

        from_addr = f"0x{topics[1][-40:]}"
        to_addr = f"0x{topics[2][-40:]}"
        decimals = 6  # Ð¿Ð¾ ÑÐ¼Ð¾Ð»ÑÐ°Ð½Ð¸Ñ (Ð½Ð°Ð¿ÑÐ¸Ð¼ÐµÑ, USDT)
        amount_raw = int(data_hex, 16)
        amount_tokens = amount_raw / (10 ** decimals)
        value_usd = amount_tokens  # Ð¿ÑÐ¸Ð±Ð»Ð¸Ð¶ÑÐ½Ð½Ð¾ (1:1, ÐµÑÐ»Ð¸ USDT/USDC)

        if value_usd < USD_THRESHOLD:
            logger.info(f"[INFO] Skipped tx ${value_usd}")
            return {"status": "ignored"}

        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        direction = "IN" if to_addr.lower() not in from_addr.lower() else "OUT"

        message = (
            f"**Whale Alert!**\n"
            f"**Amount:** `${value_usd:,.2f}`\n"
            f"**Token:** `{token_address}`\n"
            f"**Quantity:** `{amount_tokens:,.2f}` tokens\n"
            f"**Direction:** `{direction}`\n"
            f"**From:** `{from_addr}`\n"
            f"**To:** `{to_addr}`\n"
            f"**TX Hash:** [View](https://etherscan.io/tx/{tx_hash})\n"
            f"**Time:** {timestamp}"
        )

        async with httpx.AsyncClient() as client:
            await client.post(DISCORD_WEBHOOK_URL, json={"content": message})

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error"}