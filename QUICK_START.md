# Decipline — quick start

## Open the app

1. Download the Windows ZIP from https://github.com/Ferdaws-c/Decipline/releases/latest.
2. Right-click the ZIP, choose **Extract All**, and open the extracted **Decipline** folder.
3. Double-click **Decipline.exe**. Keep the whole folder together. You do not need to install Python.
4. Choose **Basic** for the simple view. Select a course, or press **+** to add one, then press **Start**.

When study time ends, press **OK** in the popup to start your break. Breaks are stored separately from study hours. **View trends** shows your progress.

**Hide** keeps the timer running in the system tray. Click its tray icon to return. **Close app** (or **×**) saves your progress and exits.

## Optional: reminders on your phone

You only need Telegram and a few minutes. This is free; no coding is needed.

1. Switch to **Expert mode** using the top bar, then open **Settings**.
2. Under **Telegram notifications**, click **How to set up Telegram** for the guide inside the app.
3. In Telegram, open the verified **@BotFather**: https://t.me/BotFather. Press **Start**, send **/newbot**, and follow the instructions. Give your bot a name and a unique username ending in **bot**.
4. BotFather sends a long code called a **token**, also known as your bot's API key. Copy the whole code and paste it into **BOT TOKEN** in Decipline.
5. Open the link to your new bot from BotFather's reply. Press **Start** and send **Hello**. It is normal if your bot does not reply.
6. Back in Decipline, click **Find my chat ID**. It fills in the number for you. Use a separate bot just for yourself so the app can identify your chat.
7. Click **Test connection**. Check Telegram for the test message.
8. Turn on **Notify me when a break ends**, then click **Save settings**. You can switch back to Basic mode afterward.

Telegram sends reminders only when a break finishes. Decipline must stay running and connected to the internet for these reminders. The timer and Trends work without internet.

If no chat is found, send a fresh **Hello** to your own bot and try again. If the token is not accepted, copy it again in full. If the bot is used by another service, create a separate bot for Decipline. If messages arrive but your phone stays silent, check Telegram's notification permissions and unmute the bot's chat.

Treat the token like a password. Your settings file stores it locally; do not share that file. If you accidentally share the token, ask BotFather to replace it.

Official Telegram instructions: https://core.telegram.org/bots/tutorial#obtain-your-bot-token

## Updating an older copy

Close the old app before opening the new one. Extract the new **Decipline** folder next to your existing settings.json, stats.json, and schedules.json files. Keep those files; they contain your settings, history, and routines. Decipline detects them beside its folder or in the parent folder.
