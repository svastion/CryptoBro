import os
import logging
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import httpx
from datetime import datetime

load_dotenv()

app = FastAPI()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ALCHEMY_URL = os.getenv("ALCHEMY_URL")
USD_THRESHOLD = 1.0

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")


async def get_token_metadata(token_address: str):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(ALCHEMY_URL, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getTokenMetadata",
                "params": [token_address]
            })
            return response.json().get("result", {})
        except Exception as e:
            logger.error(f"[ERROR] Failed to get token metadata: {e}")
            return {}


async def get_token_price(token_address: str):
    url = f"https://api.coingecko.com/api/v3/simple/token_price/ethereum?contract_addresses={token_address}&vs_currencies=usd"
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(url)
            return res.json().get(token_address.lower(), {}).get("usd", 0)
        except Exception as e:
            logger.error(f"[ERROR] Failed to get token price: {e}")
            return 0


@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        event = payload.get("event")

        if not event:
            logger.info("[INFO] No logs in event")
            return {"status": "ignored"}

        raw_logs = event.get("rawLogs", [])
        if not raw_logs:
            logger.info("[INFO] No logs in event")
            return {"status": "ignored"}

        for log in raw_logs:
            try:
                token_address = log.get("address")
                topics = log.get("topics", [])
                data = log.get("data", "0x0")

                if len(topics) < 3:
                    continue

                from_addr = "0x" + topics[1][-40:]
                to_addr = "0x" + topics[2][-40:]
                value = int(data, 16)

                # Get metadata
                meta = await get_token_metadata(token_address)
                symbol = meta.get("symbol", "UNKNOWN")
                decimals = int(meta.get("decimals", 18))
                amount = value / (10 ** decimals)

                # Get price
                price_per_token = await get_token_price(token_address)
                total_value = amount * price_per_token

                if total_value < USD_THRESHOLD:
                    logger.info(f"[INFO] Skipped tx ${total_value:.2f}")
                    continue

                # Prepare Discord alert
                tx_hash = event.get("transactionHash", "unknown")
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
                direction = "IN" if to_addr.lower() in [addr.lower() for addr in event.get("involvedAddresses", [])] else "OUT"

                message = (
                    f"**Whale Alert!**\n"
                    f"**Amount:** ${total_value:,.2f}\n"
                    f"**Token:** {symbol} `{token_address}`\n"
                    f"**Quantity:** {amount:,.2f} tokens\n"
                    f"**Direction:** {direction}\n"
                    f"**From:** `{from_addr}`\n"
                    f"**To:** `{to_addr}`\n"
                    f"**TX Hash:** https://etherscan.io/tx/{tx_hash}\n"
                    f"**Time:** {timestamp}"
                )

                if DISCORD_WEBHOOK_URL:
                    async with httpx.AsyncClient() as client:
                        await client.post(DISCORD_WEBHOOK_URL, json={"content": message})
                else:
                    logger.error("[ERROR] DISCORD_WEBHOOK_URL is not set")

            except Exception as e:
                logger.error(f"[ERROR] Failed to process log: {e}")

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"[ERROR] Failed to process webhook: {e}")
        return {"status": "error"}
