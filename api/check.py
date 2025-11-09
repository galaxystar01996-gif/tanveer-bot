from http.server import BaseHTTPRequestHandler
import os, json, requests, psycopg2
from urllib.parse import urlparse, parse_qs

# --- 1. CONFIGURATION ---
PINCODES_TO_CHECK = ['132001', '110016']
DATABASE_URL = os.environ.get('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
CRON_SECRET = os.environ.get('CRON_SECRET')

# --- 2. VERCEK HANDLER ---
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query_components = parse_qs(urlparse(self.path).query)
        auth_key = query_components.get('secret', [None])[0]

        if auth_key != CRON_SECRET:
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode())
            return

        try:
            main_logic()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok'}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

# --- 3. MAIN SCRIPT LOGIC ---
def main_logic():
    print("Starting stock check...")
    try:
        products_to_track = get_products_from_db()
    except Exception as e:
        print(f"Failed to fetch products: {e}")
        send_telegram_message(f"❌ Checker failed to connect to DB.")
        return

    in_stock_messages = []
    for product in products_to_track:
        for pincode in PINCODES_TO_CHECK:
            result = None
            if product["storeType"] == 'croma':
                result = check_croma(product, pincode)
            elif product["storeType"] == 'flipkart':
                result = check_flipkart(product, pincode)
            if result:
                in_stock_messages.append(result)

    if in_stock_messages:
        print(f"Found {len(in_stock_messages)} items. Sending message.")
        final_message = "🔥 *Stock Alert!*\n\n" + "\n\n".join(in_stock_messages)
        send_telegram_message(final_message)
    else:
        print("All items out of stock.")

# --- 4. HELPER FUNCTIONS ---

def get_products_from_db():
    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT name, url, product_id, store_type FROM products")
    products = cursor.fetchall()
    conn.close()
    products_list = [{"name": r[0], "url": r[1], "productId": r[2], "storeType": r[3]} for r in products]
    print(f"Found {len(products_list)} products.")
    return products_list

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown', 'disable_web_page_preview': True}
    requests.post(url, json=payload, timeout=10)

def check_croma(product, pincode):
    url = 'https://api.croma.com/inventory/oms/v2/tms/details-pwa/'
    payload = {"promise": {"allocationRuleID": "SYSTEM", "checkInventory": "Y", "organizationCode": "CROMA", "sourcingClassification": "EC", "promiseLines": {"promiseLine": [{"fulfillmentType": "HDEL", "itemID": product["productId"], "lineId": "1", "requiredQty": "1", "shipToAddress": {"zipCode": pincode}, "extn": {"widerStoreFlag": "N"}}]}}}
    headers = {'accept': 'application/json', 'content-type': 'application/json', 'oms-apim-subscription-key': '1131858141634e2abe2efb2b3a2a2a5d', 'origin': 'https://www.croma.com', 'referer': 'https://www.croma.com/'}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status() 
        data = res.json()
        if data.get("promise", {}).get("suggestedOption", {}).get("option", {}).get("promiseLines", {}).get("promiseLine"):
            return f'✅ *In Stock at Croma ({pincode})*\n[{product["name"]}]({product["url"]})'
    except Exception as e:
        print(f'Error checking Croma ({product["name"]}): {e}')
    return None

def check_flipkart(product, pincode):
    url = "https://2.rome.api.flipkart.com/api/3/product/serviceability"
    payload = {"requestContext": {"products": [{"productId": product["productId"]}]}, "locationContext": {"pincode": pincode}}
    headers = {
        "Accept": "application/json", "Origin": "https://www.flipkart.com", "Referer": "https://www.flipkart.com/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
        "X-User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36 FKUA/msite/0.0.3/msite/Mobile",
    }
    try:
        # We give Flipkart 30s because it can be slow
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res.raise_for_status() 
        data = res.json()
        listing = data.get("RESPONSE", {}).get(product["productId"], {}).get("listingSummary", {})
        if listing.get("serviceable") is True and listing.get("available") is True:
            return f'✅ *In Stock at Flipkart ({pincode})*\n[{product["name"]}]({product["url"]})'
    except Exception as e:
        print(f'Error checking Flipkart ({product["name"]}): {e}')
    return None