"""Plain-language, self-contained Telegram setup instructions."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QPushButton
from .qt_components import label


class TelegramHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set up Telegram notifications")
        self.resize(650, 680)
        self.setMinimumSize(540, 480)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(14)
        layout.addWidget(label("Get a reminder on your phone", "PageTitle"))
        self.instructions = QTextBrowser()
        self.instructions.setOpenExternalLinks(True)
        self.instructions.setStyleSheet("QTextBrowser { border: none; background: transparent; font-size: 13px; }")
        self.instructions.setHtml("""
        <p>You only need Telegram and a few minutes. No coding or paid account is needed.</p>
        <h3>1. Create your bot</h3>
        <p>Open Telegram and search for <a href="https://t.me/BotFather">@BotFather</a>,
        Telegram's official bot with the verified check mark. Press <b>Start</b>,
        send <b>/newbot</b>, and follow its instructions. Choose a name, then a unique
        username ending in <b>bot</b>, such as <b>MyStudyReminder_bot</b>.</p>
        <h3>2. Copy your bot token</h3>
        <p>BotFather gives you a long code called a <b>token</b> (your bot's API key).
        Copy the entire code. Return to Decipline and paste it into <b>BOT TOKEN</b>.</p>
        <h3>3. Say hello to your own bot</h3>
        <p>In BotFather's reply, open the link to the bot you just created.
        Press <b>Start</b> and send <b>Hello</b>. It is normal if the bot does not reply.</p>
        <h3>4. Find your chat ID</h3>
        <p>Back in Decipline, click <b>Find my chat ID</b>. The app fills in the number
        automatically. This tells your bot where to send your reminders.
        Use a new bot just for yourself, so the app can identify your chat.</p>
        <h3>5. Test and save</h3>
        <p>Click <b>Test connection</b> and check Telegram for a hello from Decipline.
        Turn on <b>Notify me when a break ends</b>, then click <b>Save settings</b>.</p>
        <h3>When will I get a message?</h3>
        <p>Telegram alerts you <b>only when a break finishes</b>. When study time ends,
        Decipline shows a popup on your computer. Press <b>OK</b> to start your break.
        Keep Decipline running and connected to the internet for phone alerts.</p>
        <h3>If something does not work</h3>
        <p><b>No chat found?</b> Send a fresh Hello to your own bot, then try again.<br>
        <b>Token not accepted?</b> Copy the whole token again, without extra spaces.<br>
        <b>Another app uses this bot?</b> Create a separate bot for Decipline.<br>
        <b>No phone notification?</b> Check that Telegram notifications are allowed
        on your phone and that the bot's chat is not muted.</p>
        <p><b>Keep your token private.</b> Treat it like a password. It is saved locally
        in your settings file; do not share that file. If you accidentally share the
        token, ask BotFather to replace it.</p>
        <p><a href="https://core.telegram.org/bots/tutorial#obtain-your-bot-token">Telegram's official bot guide</a></p>
        """)
        layout.addWidget(self.instructions, 1)
        close = QPushButton("Got it — back to settings")
        close.setObjectName("PrimaryButton")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
