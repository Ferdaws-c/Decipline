import json
import os

SETTINGS_PATH = "settings.json"

DEFAULT_SETTINGS = {
    "focus_time": 25,
    "short_break": 5,
    "long_break": 30,
    "sound_enabled": True,
    "autocomplete_minutes": 10,
    "telegram_enabled": False,
    "telegram_token": "",
    "telegram_chat_id": ""
}

def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Merge with defaults in case of missing keys
            res = DEFAULT_SETTINGS.copy()
            res.update(data)
            return res
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(data):
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass
