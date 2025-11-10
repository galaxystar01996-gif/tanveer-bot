from http.server import BaseHTTPRequestHandler
import os, json, requests, psycopg2, datetime, hashlib, hmac
from urllib.parse import urlparse, parse_qs

# =========================
# 🔧 CONFIGURATION
# =========================
PINCODES_TO_CHECK = ['132001']
DATABASE_URL = os.getenv('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_GROUP_ID = os.getenv('TELEGRAM_GROUP_ID')  # e.g. -4789301236
CRON_SECRET = os.getenv('CRON_SECRET')

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AMAZON_PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG")

MENTION_USERNAME = "@iamrknldeals"

# =========================
# 🧠 VERCEL HANDLER
# =========================
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        auth_key = query.get('secret', [None])[0]

        if auth_key != CRON_SECRET:
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode())
            return

        try:
            in_stock_messages, summary = main_logic()

            if in_stock_messages:
                final_message = (
                    f"🔥 *Stock Alert!* {MENTION_USERNAME}\n\n"
                    + "\n\n".join(in_stock_messages)
                )
            else:
                final_message = "❌ No items currently in stock."

            final_message += f"\n\n📊 *Summary:*\n{summary}"

            send_group_message(final_message)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'found': len(in_stock_messages)}).encode())

        except Exception as e:
            print(f"[error] {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

# =========================
# 🗃️ DATABASE
# =========================
def get_products_from_db():
    print("[info] Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT name, url, product_id, store_type, affiliate_link FROM products")
    rows = cursor.fetchall()
    conn.close()
    print(f"[info] Loaded {len(rows)} products from database.")
    return [
        {"name": r[0], "url": r[1], "productId": r[2], "storeType": r[3], "affiliateLink": r[4]}
        for r in rows
    ]

# =========================
# 💬 TELEGRAM GROUP HANDLER
# =========================
def send_group_message(message):
    """Send one message to the Telegram group."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_GROUP_ID:
        print("[warn] Missing Telegram config.")
        return

    payload = {
        'chat_id': TELEGRAM_GROUP_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"[info] ✅ Message sent to group {TELEGRAM_GROUP_ID}")
        else:
            print(f"[warn] ⚠️ Telegram send failed: {res.text}")
    except Exception as e:
        print(f"[error] Telegram send error: {e}")

# =========================
# 🏬 CROMA STOCK CHECKER
# =========================
def check_croma(product, pincode):
    """Accurate Croma stock checker — marks 'In Stock' only if truly deliverable."""
    url = 'https://api.croma.com/inventory/oms/v2/tms/details-pwa/'
    payload = {
        "promise": {
            "allocationRuleID": "SYSTEM",
            "checkInventory": "Y",
            "organizationCode": "CROMA",
            "sourcingClassification": "EC",
            "promiseLines": {"promiseLine": [{
                "fulfillmentType": "HDEL",
                "itemID": product["productId"],
                "lineId": "1",
                "requiredQty": "1",
                "shipToAddress": {"zipCode": pincode},
                "extn": {"widerStoreFlag": "N"}
            }]}
        }
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "oms-apim-subscription-key": "1131858141634e2abe2efb2b3a2a2a5d",
        "origin": "https://www.croma.com",
        "referer": "https://www.croma.com/"
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        data = res.json()

        suggested = data.get("promise", {}).get("suggestedOption", {})
        option = suggested.get("option", {})
        promise_lines = option.get("promiseLines", {}).get("promiseLine", [])
        unavailable_lines = suggested.get("unavailableLines", {}).get("unavailableLine", [])

        # Unavailable
        if unavailable_lines or not promise_lines:
            print(f"[CROMA] ❌ {product['name']} unavailable at {pincode}")
            return None

        # Available
        line = promise_lines[0]
        assignments = line.get("assignments", {}).get("assignment", [])
        if assignments and any(a.get("deliveryDate") for a in assignments):
            print(f"[CROMA] ✅ {product['name']} deliverable to {pincode}")
            return f"✅ *Croma ({pincode})*\n[{product['name']}]({product['affiliateLink'] or product['url']})"
        else:
            print(f"[CROMA] ❌ {product['name']} - No valid delivery assignment.")
            return None

    except Exception as e:
        print(f"[error] Croma check failed for {product['name']}: {e}")
        return None

# =========================
# 🛒 AMAZON CHECKER (safe)
# =========================
def check_amazon(product):
    """Currently skipping Amazon due to throttling."""
    print(f"[AMAZON] ⚠️ Skipping {product['name']} (throttled).")
    return None

# =========================
# 🚀 MAIN LOGIC
# =========================
def main_logic():
    print("[info] Starting stock check...")
    products = get_products_from_db()
    in_stock_messages = []
    total_croma, total_amazon = 0, 0
    available_croma, available_amazon = 0, 0

    for product in products:
        result = None
        if product["storeType"] == "croma":
            total_croma += 1
            for pin in PINCODES_TO_CHECK:
                result = check_croma(product, pin)
                if result:
                    available_croma += 1
                    in_stock_messages.append(result)
                    break
        elif product["storeType"] == "amazon":
            total_amazon += 1
            result = check_amazon(product)
            if result:
                available_amazon += 1
                in_stock_messages.append(result)

    summary = (
        f"🟢 *Croma:* {available_croma}/{total_croma}\n"
        f"🟡 *Amazon:* {available_amazon}/{total_amazon} (API throttled)\n"
        f"📦 *Total:* {len(in_stock_messages)} available"
    )

    print(f"[info] ✅ Found {len(in_stock_messages)} products in stock.")
    print(f"[info] Summary:\n{summary}")
    return in_stock_messages, summary
