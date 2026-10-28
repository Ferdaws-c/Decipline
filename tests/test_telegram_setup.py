"""Telegram setup stays simple, truthful, nonblocking and free of token leaks."""
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication, QLineEdit
from app import settings
from app import telegram_bot as telegram
from app.qt_settings import SettingsDialog

TOKEN = "123456:sample_secret"


class TelegramApiTests(unittest.TestCase):
    def response(self, result):
        return io.BytesIO(json.dumps({"ok": True, "result": result}).encode())

    def test_chat_discovery_ignores_groups_and_deduplicates_private_messages(self):
        updates = [{"message": {"chat": {"id": 42, "type": "private"}}},
                   {"message": {"chat": {"id": 42, "type": "private"}}},
                   {"message": {"chat": {"id": -100, "type": "supergroup"}}}]
        with patch.object(telegram.urllib.request, "urlopen", return_value=self.response(updates)) as request:
            self.assertEqual(telegram.find_private_chat_id(TOKEN), "42")
        data = json.loads(request.call_args.args[0].data)
        self.assertNotIn("offset", data)  # Looking up a chat must not consume messages.
        self.assertEqual(data["timeout"], 0)

    def test_no_messages_explains_start_and_hello(self):
        with patch.object(telegram, "_request", return_value=[]):
            with self.assertRaisesRegex(telegram.TelegramError, "press Start, and send Hello"):
                telegram.find_private_chat_id(TOKEN)

    def test_multiple_recipients_are_never_guessed(self):
        updates = [{"message": {"chat": {"id": n, "type": "private"}}} for n in (42, 43)]
        with patch.object(telegram, "_request", return_value=updates):
            with self.assertRaisesRegex(telegram.TelegramError, "More than one person"):
                telegram.find_private_chat_id(TOKEN)

    def test_invalid_token_does_not_make_a_request(self):
        with patch.object(telegram.urllib.request, "urlopen") as request:
            for token in ("", "not-a-token", "123:bad/token", "123:bad token"):
                with self.assertRaises(telegram.TelegramError):
                    telegram.find_private_chat_id(token)
            request.assert_not_called()

    def test_http_and_connection_errors_never_expose_secret_urls(self):
        for code in (400, 401, 403, 404, 409, 429, 500):
            error = HTTPError(f"https://api.telegram.org/bot{TOKEN}/getUpdates", code, TOKEN, {}, None)
            with self.subTest(code=code), patch.object(telegram.urllib.request, "urlopen", side_effect=error):
                with self.assertRaises(telegram.TelegramError) as failure:
                    telegram.find_private_chat_id(TOKEN)
                self.assertNotIn(TOKEN, str(failure.exception))
                self.assertNotIn("https://", str(failure.exception))
        with patch.object(telegram.urllib.request, "urlopen", side_effect=URLError(TOKEN)):
            with self.assertRaisesRegex(telegram.TelegramError, "internet connection"):
                telegram.find_private_chat_id(TOKEN)

    def test_unsuccessful_api_reply_and_bad_json_are_not_success(self):
        for response in (b'{"ok":false,"error_code":401}', b'not json', b'[]'):
            with patch.object(telegram.urllib.request, "urlopen", return_value=io.BytesIO(response)):
                with self.assertRaises(telegram.TelegramError):
                    telegram.send_test_message(TOKEN, "42")

    def test_test_message_and_notification_use_expected_recipient(self):
        with patch.object(telegram.urllib.request, "urlopen", return_value=self.response({"message_id": 1})) as request:
            telegram.send_test_message(TOKEN, "42")
            body = json.loads(request.call_args.args[0].data)
            self.assertEqual(body["chat_id"], "42")
            self.assertIn("when your break ends", body["text"])
        with patch.object(telegram, "_request", side_effect=telegram.TelegramError("Failed")), patch("builtins.print") as logged:
            self.assertFalse(telegram.send_telegram_message("Break over", TOKEN, "42"))
            logged.assert_not_called()


class TelegramSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        context = patch.object(settings, "SETTINGS_PATH", str(Path(temp.name)/"settings.json"))
        context.start()
        self.addCleanup(context.stop)
        settings.save_settings({**settings.DEFAULT_SETTINGS, "experience_mode": "expert"})
        self.dialog = SettingsDialog()
        self.addCleanup(self.dialog.deleteLater)
        self.addCleanup(self.dialog.close)

    def wait_for_result(self):
        deadline = time.monotonic()+2
        while self.dialog._telegram_busy and time.monotonic()<deadline:
            self.app.processEvents()
            time.sleep(.001)
        self.assertFalse(self.dialog._telegram_busy)

    def enter_token(self):
        self.dialog.entry_token.setText(TOKEN)

    def test_help_button_opens_self_contained_guide_without_network_or_saving(self):
        with patch.object(telegram.urllib.request, "urlopen") as network, patch('app.qt_settings.save_settings') as save:
            self.dialog.telegram_help_btn.click()
            guide = self.dialog._telegram_help_dialog
            self.assertTrue(guide.isVisible())
            text = guide.instructions.toPlainText()
            for expected in ("/newbot", "BOT TOKEN", "Find my chat ID", "Test connection", "Save settings", "only when a break finishes"):
                self.assertIn(expected, text)
            guide.accept()
            self.assertIsNone(self.dialog._telegram_help_dialog)
            network.assert_not_called()
            save.assert_not_called()

    def test_missing_details_are_explained_before_network(self):
        with patch.object(telegram.urllib.request, "urlopen") as network:
            self.dialog.find_chat_btn.click()
            self.assertIn("token first", self.dialog.telegram_status.text())
            self.enter_token()
            self.dialog.test_telegram_btn.click()
            self.assertIn("Find my chat ID", self.dialog.telegram_status.text())
            network.assert_not_called()

    def test_find_chat_is_nonblocking_and_fills_only_after_completion(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def find(token):
            started.set()
            release.wait(2)
            return "42"
        self.enter_token()
        with patch.object(telegram, "find_private_chat_id", side_effect=find):
            self.dialog.find_chat_btn.click()
            self.assertTrue(started.wait(1))
            self.assertTrue(self.dialog._telegram_busy)
            self.assertFalse(self.dialog.test_telegram_btn.isEnabled())
            self.assertEqual(self.dialog.entry_chat_id.text(), "")
            self.app.processEvents()
            release.set()
            self.wait_for_result()
        self.assertEqual(self.dialog.entry_chat_id.text(), "42")
        self.assertTrue(self.dialog.test_telegram_btn.isEnabled())
        self.assertIn("Chat ID found", self.dialog.telegram_status.text())
        self.assertEqual(settings.load_settings()["telegram_chat_id"], "")

    def test_test_failure_does_not_claim_message_was_sent(self):
        self.enter_token()
        self.dialog.entry_chat_id.setText("42")
        with patch.object(telegram, "send_test_message", side_effect=telegram.TelegramError("Token not accepted")):
            self.dialog.test_telegram_btn.click()
            self.wait_for_result()
        self.assertEqual(self.dialog.telegram_status.text(), "Token not accepted")

    def test_successful_test_only_shows_success_after_api_finishes(self):
        self.enter_token()
        self.dialog.entry_chat_id.setText("42")
        with patch.object(telegram, "send_test_message") as send:
            self.dialog.test_telegram_btn.click()
            self.wait_for_result()
            send.assert_called_once_with(TOKEN, "42")
        self.assertIn("Test message sent", self.dialog.telegram_status.text())

    def test_changed_details_ignore_stale_chat_lookup(self):
        self.enter_token()
        self.dialog.entry_chat_id.setText("99")
        self.dialog._telegram_finished("find", (TOKEN, ""), {"ok": True, "value": "42"})
        self.assertEqual(self.dialog.entry_chat_id.text(), "99")
        self.assertIn("details changed", self.dialog.telegram_status.text())

    def test_token_is_masked_and_only_explicit_save_keeps_credentials(self):
        self.enter_token()
        self.assertEqual(self.dialog.entry_token.echoMode(), QLineEdit.EchoMode.Password)
        self.dialog.entry_chat_id.setText("42")
        self.dialog.chk_tg.setChecked(True)
        self.assertEqual(settings.load_settings()["telegram_token"], "")
        self.dialog._save()
        saved = settings.load_settings()
        self.assertEqual(saved["telegram_token"], TOKEN)
        self.assertEqual(saved["telegram_chat_id"], "42")
        self.assertTrue(saved["telegram_enabled"])


if __name__ == '__main__':
    unittest.main()
