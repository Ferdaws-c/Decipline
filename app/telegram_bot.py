import threading
import urllib.request
import urllib.parse
import json
import urllib.error
import re


class TelegramError(Exception):
    """A user-facing failure that never includes a bot token or request URL."""


def _request(method, token, data):
    if not token:
        raise TelegramError("Paste the full bot token from @BotFather first.")
    if not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
        raise TelegramError("Copy the full bot token from @BotFather, including the numbers and colon. Do not include spaces.")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    code = None
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.load(response)
        if not isinstance(result, dict):
            raise TelegramError("Telegram returned an unexpected reply. Please try again.")
        if result.get("ok"):
            return result.get("result")
        code = result.get("error_code")
    except urllib.error.HTTPError as error:
        code = error.code
    except (urllib.error.URLError, OSError):
        raise TelegramError("Could not reach Telegram. Check your internet connection and try again.") from None
    except (ValueError, TypeError):
        raise TelegramError("Telegram returned an unexpected reply. Please try again.") from None
    if code == 401 or code == 404:
        message = "The bot token was not accepted. Copy the full token from @BotFather and try again."
    elif code == 409 or (code == 400 and method == "getUpdates"):
        message = "This bot may be used by another service. Create a separate bot for Decipline with @BotFather."
    elif code == 403:
        message = "Open your bot in Telegram, unblock it if needed, and press Start. Then try again."
    elif code == 429:
        message = "Telegram is receiving too many requests. Wait a minute, then try again."
    else:
        message = "Telegram could not send the message. Open your bot, press Start, and check the chat ID."
    raise TelegramError(message)


def find_private_chat_id(token):
    """Find one private recipient without consuming updates or guessing between people."""
    updates = _request("getUpdates", token, {"timeout": 0, "limit": 100})
    chats = {str(chat["id"]) for update in updates
             if (chat := update.get("message", {}).get("chat", {})).get("type") == "private" and "id" in chat}
    if not chats:
        raise TelegramError("Open your own bot in Telegram, press Start, and send Hello. Then click Find my chat ID again.")
    if len(chats) != 1:
        raise TelegramError("More than one person has messaged this bot. Enter your own chat ID, or create a new bot just for Decipline.")
    return chats.pop()


def send_test_message(token, chat_id):
    _request("sendMessage", token, {"chat_id": chat_id,
             "text": "Hello from Decipline! Telegram is connected. Future alerts arrive when your break ends."})

def send_telegram_message(message: str, token: str, chat_id: str):
    """Sends a message synchronously via Telegram API."""
    if not token or not chat_id:
        return
        
    try:
        _request("sendMessage", token, {"chat_id": chat_id, "text": message})
        return True
    except TelegramError:
        # Never log a urllib exception: its URL contains the secret bot token.
        return False

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
