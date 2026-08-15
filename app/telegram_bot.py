import threading
import urllib.request
import urllib.parse
import json

def send_telegram_message(message: str, token: str, chat_id: str):
    """Sends a message synchronously via Telegram API."""
    if not token or not chat_id:
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
    }
    
    try:
        req = urllib.request.Request(url, method="POST")
        req.add_header("Content-Type", "application/json")
        encoded_data = json.dumps(data).encode("utf-8")
        urllib.request.urlopen(req, data=encoded_data, timeout=5)
    except Exception as e:
        print(f"Telegram notification failed: {e}")

def notify_async(message: str):
    """Dispatches the notification in a background thread using saved settings."""
    from .settings import load_settings
    settings = load_settings()
    
    if not settings.get("telegram_enabled", False):
        return
        
    token = settings.get("telegram_token", "")
    chat_id = settings.get("telegram_chat_id", "")
    
    if not token or not chat_id:
        return
        
    thread = threading.Thread(target=send_telegram_message, args=(message, token, chat_id), daemon=True)
    thread.start()
