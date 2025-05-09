import os
import logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from datetime import datetime
import httpx

load_dotenv()

app = FastAPI()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
USD_THRESHOLD = 1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

TOKEN_SYMBOLS = {
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": "USDC",
    "0x6b175474e89094c44da98b954eedeac495271d0f": "DAI",
    "0xdac17f958d2ee523a2206206994597c13d831ec7": "USDT",
    "0x514910771af9ca656af840dff83e8264ecf986ca": "LINK",
    "0x0000000000000000000000000000000000000000": "ETH"
}

@app.post("/")
async def webhook_listener(request: Request):
    try:
        data = await request.json()

        logs = data.get("block", {}).get("logs", [])
        if not logs:
            logger.info("[INFO] No logs in event")
            return {"status": "ignored"}

        for log in logs:
            try:
                tx = log.get("transaction", {})
                token_address = tx.get("to", {}).get("address", "unknown")
                from_address = tx.get("from", {}).get("address", "unknown")
                to_address = tx.get("to", {}).get("address", "unknown")
                value_raw = int(tx.get("value", 0))
                value = value_raw / 1e6  # For USDC/USDT/DAI 6 decimals
                symbol = TOKEN_SYMBOLS.get(token_address.lower(), "UNKNOWN")
                tx_hash = tx.get("hash", "unknown")
                timestamp = data["block"].get("timestamp")

                if value < USD_THRESHOLD:
                    logger.info(f"[INFO] Skipped tx under threshold: ${value}")
                    continue

                time_str = datetime.utcfromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M UTC")

                embed = {
                    "embeds": [
                        {
                            "title": "ð¨ Whale Alert!",
                            "color": 0x3498db,
                            "fields": [
                                {"name": "Amount", "value": f"**${value:,.2f} {symbol}**", "inline": True},
                                {"name": "Token Address", "value": f"`{token_address}`", "inline": False},
                                {"name": "From", "value": f"`{from_address}`", "inline": False},
                                {"name": "To", "value": f"`{to_address}`", "inline": False},
                                {"name": "TX", "value": f"[View on Etherscan](https://etherscan.io/tx/{tx_hash})", "inline": False},
                                {"name": "Time", "value": time_str, "inline": True}
                            ],
                            "footer": {"text": "CryptoBro | Whale Tracker"}
                        }
                    ]
                }

                async with httpx.AsyncClient() as client:
                    await client.post(DISCORD_WEBHOOK_URL, json=embed)

            except Exception as e:
                logger.error(f"[ERROR] Error processing log entry: {e}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error"}
