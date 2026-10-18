import json
import os
import tempfile
import logging
from .paths import data_path

SETTINGS_PATH = data_path("settings.json")

DEFAULT_SETTINGS = {
    "experience_mode": "basic",
    "expert_course_path": True,
    "onboarding_completed": False,
    "focus_time": 25,
    "short_break": 5,
    "long_break": 30,
    "sound_enabled": True,
    "autocomplete_minutes": 10,
    "telegram_enabled": False,
    "telegram_token": "",
    "telegram_chat_id": ""
}


def get_experience_mode():
    mode = load_settings().get("experience_mode", "basic")
    return mode if mode in ("basic", "expert") else "basic"

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
    temporary = None
    try:
        path = os.path.abspath(SETTINGS_PATH)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                dir=os.path.dirname(path), delete=False) as f:
            temporary = f.name
            json.dump(data, f, indent=2)
        os.replace(temporary, path)
        return True
    except Exception:
        logging.getLogger(__name__).exception("Could not save settings")
        return False
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
