import os, json, logging, httpx
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
logging.basicConfig(level=logging.INFO)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Сопоставление адресов API и ключей по сети
SCANNERS = {
    "ethereum": {
        "api": os.getenv("ETHERSCAN_API_URL"),
        "key": os.getenv("ETHERSCAN_API_KEY"),
        "label": "Etherscan"
    },
    "bsc": {
        "api": os.getenv("BSCSCAN_API_URL"),
        "key": os.getenv("BSCSCAN_API_KEY"),
        "label": "BscScan"
    },
    "avalanche": {
        "api": os.getenv("SNOWSCAN_API_URL"),
        "key": os.getenv("SNOWSCAN_API_KEY"),
        "label": "SnowScan"
    },
    "arbitrum": {
        "api": os.getenv("ARBISCAN_API_URL"),
        "key": os.getenv("ARBISCAN_API_KEY"),
        "label": "Arbiscan"
    },
    "optimism": {
        "api": os.getenv("OPTIMISM_API_URL"),
        "key": os.getenv("OPTIMISM_API_KEY"),
        "label": "OptimismScan"
    }
}

ETHPLORER_API_KEY = os.getenv("ETHPLORER_API_KEY", "freekey")
COINGECKO_URL = os.getenv("COINGECKO_API", "https://api.coingecko.com/api/v3")

def format_eth(hex_val):
    try:
        return int(hex_val, 16) / 1e18
    except:
        return 0

async def get_token_info(contract, chain="ethereum"):
    symbol, name, price, source = None, None, None, None

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{COINGECKO_URL}/coins/{chain}/contract/{contract}")
            if r.status_code == 200:
                d = r.json()
                symbol = d.get("symbol", "").upper()
                name = d.get("name", "")
                price = d.get("market_data", {}).get("current_price", {}).get("usd")
                source = "Coingecko"
                return symbol, name, price, source
    except:
        pass

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.ethplorer.io/getTokenInfo/{contract}?apiKey={ETHPLORER_API_KEY}")
            d = r.json()
            symbol = d.get("symbol", "").upper()
            name = d.get("name", "")
            price = d.get("price", {}).get("rate")
            source = "Ethplorer"
            return symbol, name, price, source
    except:
        pass

    scan = SCANNERS.get(chain)
    if scan:
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(scan["api"], params={
                    "module": "token",
                    "action": "tokeninfo",
                    "contractaddress": contract,
                    "apikey": scan["key"]
                })
                d = r.json()
                if d["status"] == "1":
                    info = d["result"][0]
                    symbol = info.get("symbol", "").upper()
                    name = info.get("tokenName", "")
                    source = scan["label"]
                    return symbol, name, None, source
        except:
            pass

    return symbol, name, price, source

@app.post("/webhook")
async def webhook_listener(request: Request):
    payload = await request.json()
    block = payload.get("event", {}).get("block", {})
    logs = block.get("logs", [])
    if not logs:
        return {"status": "no_logs"}

    for log in logs:
        tx = log.get("transaction", {})
        if not tx:
            continue

        value = format_eth(tx.get("value", "0x0"))
        if value == 0:
            continue

        from_addr = tx.get("from", {}).get("address")
        to_addr = tx.get("to", {}).get("address")
        tx_hash = tx.get("hash")
        contract = log.get("account", {}).get("address", "")
        chain = payload.get("network", "ethereum")

        symbol, name, price_usd, provider = await get_token_info(contract, chain)

        color = 0x00FF00 if price_usd else 0xFF0000
        price_str = f"{price_usd:.4f} USDT" if price_usd else "Unknown"

        embed = {
            "title": f"🔔 New {chain.capitalize()} Transaction",
            "description": f"**Symbol:** {symbol or 'N/A'}
"
                           f"**Name:** {name or 'N/A'}
"
                           f"**Amount:** `{value:.4f}`
"
                           f"**Price:** `{price_str}`
"
                           f"**From:** `{from_addr}`
"
                           f"**To:** `{to_addr}`
"
                           f"[TX Link](https://{chain}.etherscan.io/tx/{tx_hash}) | via `{provider or 'N/A'}`",
            "color": color
        }

        await httpx.AsyncClient().post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})

    return {"status": "ok"}