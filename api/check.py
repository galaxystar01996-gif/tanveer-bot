from http.server import BaseHTTPRequestHandler
import os, json, requests, psycopg2
from urllib.parse import urlparse, parse_qs

# --- 1. CONFIGURATION ---
PINCODES_TO_CHECK = ['132001']
DATABASE_URL = os.environ.get('DATABASE_URL')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
# This secret MUST be set in your Vercel Environment Variables
CRON_SECRET = os.environ.get('CRON_SECRET')

# --- 2. VERCEK HANDLER ---
# This is the main entrypoint for Vercel
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse the URL to check for our secret key
        query_components = parse_qs(urlparse(self.path).query)
        auth_key = query_components.get('secret', [None])[0]

        # 1. Check if the secret is valid
        if auth_key != CRON_SECRET:
            self.send_response(401) # Unauthorized
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Unauthorized. Check your CRON_SECRET.'}).encode())
            return

        # 2. If valid, run the main stock checking logic
        try:
            # Call your main logic function
            in_stock_messages = main_logic()
            
            # Send the final report if anything is in stock
            if in_stock_messages:
                print(f"Found {len(in_stock_messages)} items in stock. Sending Telegram message.")
                final_message = "🔥 *Stock Alert!*\n\n" + "\n\n".join(in_stock_messages)
                send_telegram_message(final_message)
            else:
                print("All items out of stock. No message sent.")

            # Send a 200 OK response back to the cron job
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'found': len(in_stock_messages)}).encode())
            
        except Exception as e:
            # If anything fails, send a 500 error
            print(f"An error occurred: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

# --- 3. DATABASE: FETCH PRODUCTS ---
def get_products_from_db():
    print("Connecting to database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT name, url, product_id, store_type FROM products")
    products = cursor.fetchall()
    conn.close()
    
    products_list = [
        {"name": row[0], "url": row[1], "productId": row[2], "storeType": row[3]}
        for row in products
    ]
    print(f"Found {len(products_list)} products in the database.")
    return products_list

# --- 4. TELEGRAM SENDER ---
def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram BOT TOKEN not set. Skipping message.")
        return

    # Your hardcoded list of chat IDs
    chat_ids = ['7992845749', '984016385' , '6644657779' , '8240484793' , '1813686494' ,'1438419270' ,'939758815' , '7500224400' , '8284863866' , '837532484' , '667911343' , '1476695901' , '6878100797' , '574316265' , '1460192633' , '978243265' ,'5871190519' ]
    
    print(f"Sending message to {len(chat_ids)} users...")

    for chat_id in chat_ids:
        if not chat_id.strip():
            continue
            
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id.strip(),
            'text': message,
            'parse_mode': 'Markdown',
            'disable_web_page_preview': True
        }
        
        try:
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print(f"Failed to send message to {chat_id}: {e}")

# --- 5. CROMA CHECKER ---
def check_croma(product, pincode):
    url = 'https://api.croma.com/inventory/oms/v2/tms/details-pwa/'
    payload = {"promise": {"allocationRuleID": "SYSTEM", "checkInventory": "Y", "organizationCode": "CROMA", "sourcingClassification": "EC", "promiseLines": {"promiseLine": [{"fulfillmentType": "HDEL", "itemID": product["productId"], "lineId": "1", "requiredQty": "1", "shipToAddress": {"zipCode": pincode}, "extn": {"widerStoreFlag": "N"}}]}}}
    headers = {'accept': 'application/json', 'content-type': 'application/json', 'oms-apim-subscription-key': '1131858141634e2abe2efb2b3a2a2a5d', 'origin': 'https.www.croma.com', 'referer': 'https.www.croma.com/'}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        res.raise_for_status() 
        data = res.json()
        if data.get("promise", {}).get("suggestedOption", {}).get("option", {}).get("promiseLines", {}).get("promiseLine"):
            return f'✅ *In Stock at Croma ({pincode})*\n[{product["name"]}]({product["url"]})'
    except Exception as e:
        print(f'Error checking Croma ({product["name"]}): {e}')
    return None

# --- 6. FLIPKART CHECKER ---
def check_flipkart(product, pincode):
    url = "https://2.rome.api.flipkart.com/api/3/product/serviceability"
    payload = {
        "requestContext": {"products": [{"productId": product["productId"]}]},
        "locationContext": {"pincode": pincode}
    }
    headers = {
        "Accept": "application/json", "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive", "Content-Type": "application/json",
        "Origin": "https.www.flipkart.com", "Referer": "https.www.flipkart.com/",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36",
        "X-User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36 FKUA/msite/0.0.3/msite/Mobile",
        "flipkart_secure": "true", "DNT": "1", "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-site",
        "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "sec-ch-ua-mobile": "?1", "sec-ch-ua-platform": '"Android"',
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=30)
        res.raise_for_status() 
        data = res.json()
        listing = data.get("RESPONSE", {}).get(product["productId"], {}).get("listingSummary", {})
        
        if listing.get("serviceable") is True and listing.get("available") is True:
            return f'✅ *In Stock at Flipkart ({pincode})*\n[{product["name"]}]({product["url"]})'
    except Exception as e:
        print(f'Error checking Flipkart ({product["name"]}): {e}')
    return None

# --- 7. MAIN LOGIC ---
# I've moved your main() code into this function so the Vercel handler can call it
def main_logic():
    print("Starting stock check...")
    try:
        products_to_track = get_products_from_db()
    except Exception as e:
        print(f"Failed to fetch products from database: {e}")
        send_telegram_message(f"❌ Your checker script failed to connect to the database.")
        return [] # Return empty list on failure

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
    
    return in_stock_messages