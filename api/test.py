import datetime
import hashlib
import hmac
import json
import requests
from urllib.parse import urlparse

# --- CONFIG ---
ACCESS_KEY = "AKPA5DO1Y31762745131"
SECRET_KEY = "cRV7nGhGlGRjgFCEpMrJaV7gWkBqIsjR/NFqxIH0"
PARTNER_TAG = "deepakkum0472-21"
ASIN = "B0CX59H5W7"  # Example: iPhone 15
REGION = "eu-west-1"
SERVICE = "ProductAdvertisingAPI"
ENDPOINT = "https://webservices.amazon.in/paapi5/getitems"

# --- SIGNING HELPERS ---
def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def get_signature_key(key, date_stamp, region_name, service_name):
    k_date = sign(("AWS4" + key).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region_name)
    k_service = sign(k_region, service_name)
    k_signing = sign(k_service, "aws4_request")
    return k_signing

# --- MAIN FUNCTION ---
def check_amazon_stock(asin):
    method = "POST"
    t = datetime.datetime.utcnow()
    amz_date = t.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = t.strftime("%Y%m%d")

    payload = {
        "ItemIds": [asin],
        "Resources": [
            "ItemInfo.Title",
            "Offers.Listings.Price",
            "Offers.Listings.Availability.Message"
        ],
        "PartnerTag": PARTNER_TAG,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.in"
    }

    canonical_uri = "/paapi5/getitems"
    canonical_headers = (
        f"content-encoding:amz-1.0\n"
        f"host:{urlparse(ENDPOINT).netloc}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems\n"
    )
    signed_headers = "content-encoding;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(json.dumps(payload).encode("utf-8")).hexdigest()
    canonical_request = f"{method}\n{canonical_uri}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"

    algorithm = "AWS4-HMAC-SHA256"
    credential_scope = f"{date_stamp}/{REGION}/{SERVICE}/aws4_request"
    string_to_sign = (
        f"{algorithm}\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    signing_key = get_signature_key(SECRET_KEY, date_stamp, REGION, SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization_header = (
        f"{algorithm} Credential={ACCESS_KEY}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Content-Encoding": "amz-1.0",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Amz-Date": amz_date,
        "X-Amz-Target": "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.GetItems",
        "Authorization": authorization_header,
        "Accept": "application/json, text/javascript",
        "Host": urlparse(ENDPOINT).netloc,
    }

    r = requests.post(ENDPOINT, headers=headers, data=json.dumps(payload))
    print(f"Status: {r.status_code}")

    try:
        data = r.json()
    except Exception:
        print("❌ Failed to parse JSON response.")
        print(r.text)
        return

    if "ItemsResult" in data:
        item = data["ItemsResult"]["Items"][0]
        title = item["ItemInfo"]["Title"]["DisplayValue"]
        availability = item["Offers"]["Listings"][0]["Availability"]["Message"]
        price = item["Offers"]["Listings"][0]["Price"]["DisplayAmount"]

        print(f"📦 {title}")
        print(f"💰 {price}")
        print(f"✅ Availability: {availability}")
    else:
        print("⚠️ Error:", data.get("Errors", data))

# --- RUN ---
if __name__ == "__main__":
    check_amazon_stock(ASIN)
