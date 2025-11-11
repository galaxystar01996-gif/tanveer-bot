import requests
import json

# Your Telegram Bot Token and Chat ID
TELEGRAM_BOT_TOKEN = "8483039531:AAE4IaJREGOeMsTLGxijyOLlLUeLnYnUvbo"
TELEGRAM_GROUP_ID = "-5021367200"

# The message to send
MESSAGE = "✅ Test message from external script. If you see this, the bot permissions are correct!"

def send_test_message():
    """Sends a test message to the specified Telegram group."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    payload = {
        "chat_id": TELEGRAM_GROUP_ID,
        "text": MESSAGE,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    print(f"Attempting to send message to Chat ID: {TELEGRAM_GROUP_ID}...")
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        
        if res.status_code == 200:
            print("\n--- Success ---")
            print("✅ Message delivered successfully!")
        else:
            print("\n--- Failure ---")
            print(f"❌ Telegram send failed with status code {res.status_code}")
            print(f"API Response: {res.text}")
            
    except Exception as e:
        print(f"\n❌ An exception occurred: {e}")

if __name__ == "__main__":
    # Make sure you have 'requests' installed: pip install requests
    send_test_message()