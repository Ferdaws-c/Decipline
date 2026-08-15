def get_daily_prompt():
    return """=== DECIPLINE APP — DAILY SCHEDULE FORMAT ===

You are generating a DAILY schedule in JSON format for the Decipline productivity app.
Follow every rule below exactly. Do not deviate.

──────────────────────────────────────────────
JSON FORMAT (List of objects):
──────────────────────────────────────────────
[
  {
    "time": "08:00",
    "text": "Task Name",
    "duration": "25 min",
    "notes": "Optional notes"
  }
]

──────────────────────────────────────────────
POMODORO RULES (CRITICAL — build schedule around these):
──────────────────────────────────────────────
1. All deep focus / study / work tasks MUST be exactly 25 min blocks.
2. After every 25 min work block, leave a 5 min gap before the next block (the app handles the break).
3. After every 4th work block (= 2 hours of work), add a single task:
      "text": "Long Break", "duration": "30 min"
4. Administrative tasks can be 15 min or 30 min blocks.
5. Meals and personal time use 30 min or 60 min blocks.
6. Never schedule two consecutive 25 min work rows — always respect the 5 min gap.
7. The schedule must start at the wake-up time you are given.
8. Total working blocks per day: 8 to 12.

──────────────────────────────────────────────
BLANK-FILLING RULES:
──────────────────────────────────────────────
If the user gives you a rough outline:
- Fill the exact time using their wake time as the anchor.
- Expand each subject into 25 min Pomodoro-sized chunks.
- Add realistic transition time (5–10 min) between different subject areas.
- For unspecified slots, use: "Deep Work Block".

──────────────────────────────────────────────
OUTPUT INSTRUCTIONS:
──────────────────────────────────────────────
1. Output ONLY valid JSON inside a ```json codeblock.
2. Do not output python scripts or excel files. Just raw JSON.
3. The Time format must be 24-hour HH:MM (e.g. "08:00", "14:30").

=== END OF FORMAT INSTRUCTIONS ===
"""

def get_weekly_prompt():
    return """=== DECIPLINE APP — WEEKLY SCHEDULE FORMAT ===

You are generating a WEEKLY schedule in JSON format for the Decipline productivity app.
Follow every rule below exactly. Do not deviate.

──────────────────────────────────────────────
JSON FORMAT (Object with day keys):
──────────────────────────────────────────────
{
  "Monday": [
    {
      "time": "08:00",
      "text": "Task Name",
      "duration": "25 min",
      "notes": "Optional notes"
    }
  ],
  "Tuesday": [
    ...
  ]
}

──────────────────────────────────────────────
POMODORO RULES (CRITICAL — build schedule around these):
──────────────────────────────────────────────
1. All deep focus / study / work tasks MUST be exactly 25 min blocks.
2. After every 25 min work block, leave a 5 min gap before the next block (the app handles the break).
3. After every 4th work block (= 2 hours of work), add a single task:
      "text": "Long Break", "duration": "30 min"
4. Administrative tasks can be 15 min or 30 min blocks.
5. Meals and personal time use 30 min or 60 min blocks.
6. Never schedule two consecutive 25 min work rows — always respect the 5 min gap.
7. The schedule must start at the wake-up time you are given.
8. Total working blocks per day: 8 to 12.

──────────────────────────────────────────────
BLANK-FILLING RULES:
──────────────────────────────────────────────
If the user gives you a rough outline:
- Fill the exact time using their wake time as the anchor.
- Expand each subject into 25 min Pomodoro-sized chunks.
- Add realistic transition time (5–10 min) between different subject areas.
- For unspecified slots, use: "Deep Work Block".

──────────────────────────────────────────────
OUTPUT INSTRUCTIONS:
──────────────────────────────────────────────
1. Output ONLY valid JSON inside a ```json codeblock.
2. Do not output python scripts or excel files. Just raw JSON.
3. The Time format must be 24-hour HH:MM (e.g. "08:00", "14:30").

=== END OF FORMAT INSTRUCTIONS ===
"""
