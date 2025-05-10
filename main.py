import os
import json
import logging
import httpx
from fastapi import FastAPI, Request
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
ETHERSCAN_API_URL = os.getenv("ETHERSCAN_API_URL", "https://api.etherscan.io/api")

logging.basicConfig(level=logging.INFO)

async def fetch_tx_details_from_etherscan(tx_hash):
    try:
        url = f"{ETHERSCAN_API_URL}?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={ETHERSCAN_API_KEY}"
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            data = response.json().get("result", {})
            return data
    except Exception as e:
        logging.error(f"[ERROR] Etherscan API failed: {e}")
        return {}

def format_transaction_message(event):
    try:
        block_data = event.get("block", {})
        block_number = block_data.get("number", "Unknown")
        block_hash = block_data.get("hash", "Unknown")
        timestamp = block_data.get("timestamp", "Unknown")
        logs = block_data.get("logs", [])
        messages = []

        for log in logs:
            tx = log.get("transaction", {})
            from_address = tx.get("from", {}).get("address", "Unknown")
            to_address = tx.get("to", {}).get("address", "Unknown")
            tx_hash = tx.get("hash", "Unknown")
            value_hex = tx.get("value", "0x0")
            topics = log.get("topics", [])
            token_transfer = len(topics) > 0 and topics[0].startswith("0xddf252ad")

            value_eth = int(value_hex, 16) / 1e18
            message = (
                f"🚨 **New Transaction**\n**Hash:** {tx_hash}
"
                f"**Block:** `{block_number}`
"
                f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})
"
                f"**From:** `{from_address}`
"
                f"**To:** `{to_address}`
"
                f"**Value:** `{value_eth:.6f} ETH`
"
            )
            if token_transfer:
                message += "**Type:** ðª Token Transfer
"
            message += "----------------------------"
            messages.append(message)

        if not messages:
            txs = [log.get("transaction", {}) for log in logs]
            if not txs:
                return ["No logs found, but transaction received."]
            else:
                return ["No transaction logs in this block."]
        return messages
    except Exception as e:
        logging.error(f"[ERROR] Formatting message failed: {e}")
        return [f"â Error parsing transaction."]

@app.post("/webhook")
async def webhook_listener(request: Request):
    try:
        payload = await request.json()
        logging.info(f"Payload received: {json.dumps(payload)[:500]}...")

        messages = []
        logs = payload.get("block", {}).get("logs", [])
        if not logs:
            transactions = payload.get("block", {}).get("transactions", [])
            for tx in transactions:
                tx_hash = tx.get("hash")
                if tx_hash:
                    details = await fetch_tx_details_from_etherscan(tx_hash)
                    message = (
                        f"ð **Transaction Info via Etherscan**
"
                        f"**Tx Hash:** [`{tx_hash}`](https://etherscan.io/tx/{tx_hash})
"
                        f"**From:** `{details.get("from", "N/A")}`
"
                        f"**To:** `{details.get("to", "N/A")}`
"
                        f"**Gas:** `{details.get("gas", "N/A")}`
"
                        f"**Nonce:** `{details.get("nonce", "N/A")}`
"
                        f"**Input (method):** `{details.get("input", "")[:10]}...`
"
                        "----------------------------"
                    )
                    messages.append(message)
        else:
            messages = format_transaction_message(payload)

        async with httpx.AsyncClient() as client:
            for msg in messages:
                await client.post(DISCORD_WEBHOOK_URL, json={"content": msg})

        return {"status": "ok"}
    except Exception as e:
        logging.error(f"[ERROR] Webhook processing failed: {e}")
        return {"status": "error", "details": str(e)}