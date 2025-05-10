import os, json, logging, httpx
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
logging.basicConfig(level=logging.INFO)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
COINGECKO_URL = "https://api.coingecko.com/api/v3"
ETHPLORER_URL = f"https://api.ethplorer.io/getTokenInfo"
ETHERSCAN_URL = f"https://api.etherscan.io/api"

async def get_token_info(address):
    headers = {"accept": "application/json"}
    symbol, name, price, provider = None, None, None, None

    try:
        # Try Coingecko
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{COINGECKO_URL}/coins/ethereum/contract/{address}")
            if r.status_code == 200:
                d = r.json()
                symbol = d.get("symbol", "").upper()
                name = d.get("name", "")
                price = d.get("market_data", {}).get("current_price", {}).get("usd")
                provider = "Coingecko"
    except:
        pass

    if not symbol:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{ETHPLORER_URL}/{address}?apiKey={os.getenv('ETHPLORER_API_KEY')}")
                if r.status_code == 200:
                    d = r.json()
                    symbol = d.get("symbol", "").upper()
                    name = d.get("name", "")
                    price = d.get("price", {}).get("rate")
                    provider = "Ethplorer"
        except:
            pass

    if not symbol:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{ETHERSCAN_URL}?module=token&action=tokeninfo&contractaddress={address}&apikey={os.getenv('ETHERSCAN_API_KEY')}")
                d = r.json()
                if d["status"] == "1":
                    d = d["result"]
                    symbol = d[0].get("symbol", "").upper()
                    name = d[0].get("tokenName", "")
                    price = None
                    provider = "Etherscan"
        except:
            pass

    return symbol, name, price, provider

def format_eth(value_hex):
    try:
        return int(value_hex, 16) / 1e18
    except:
        return 0

@app.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
        logs = payload.get("event", {}).get("block", {}).get("logs", [])
        if not logs:
            logging.info("No logs in block")
            return {"status": "no_logs"}

        for log in logs:
            tx = log.get("transaction", {})
            from_address = tx.get("from", {}).get("address")
            to_address = tx.get("to", {}).get("address")
            value = format_eth(tx.get("value", "0x0"))
            hash_ = tx.get("hash")

            if value == 0:
                continue

            contract = log.get("account", {}).get("address")
            symbol, name, price_usdt, provider = await get_token_info(contract)

            embed_color = 0x00FF00 if price_usdt else 0xFF0000
            price_str = f"{price_usdt:.4f} USDT" if price_usdt else "Unknown"

            embed = {
                "title": "New Token Transfer",
                "description": f"**Symbol:** {symbol or 'N/A'}\n**Name:** {name or 'N/A'}\n**Amount:** `{value:.4f}`\n**Price:** `{price_str}`\n**From:** `{from_address}`\n**To:** `{to_address}`\n**[View Tx](https://etherscan.io/tx/{hash_})` via {provider or 'unknown'}`",
                "color": embed_color
            }

            await httpx.AsyncClient().post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})

        return {"status": "ok"}

    except Exception as e:
        logging.error(f"[ERROR] {e}")
        return {"status": "error", "detail": str(e)}