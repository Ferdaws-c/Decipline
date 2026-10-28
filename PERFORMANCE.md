# Performance and product validation

Measured locally on Windows with Python 3.13 / PyQt6, comparing source revision `5f439ef` with the current source. Qt ran offscreen; results describe this machine.

| Operation | Before | After |
| --- | ---: | ---: |
| Reset a paused timer | 2,001.98 ms | 0.08 ms |
| Advance task, refresh and paint 100 tasks | 14.65 ms | 8.91 ms |
| Advance task, refresh and paint 1,000 tasks | 46.08 ms | 18.39 ms |
| Advance task, refresh and paint 5,000 tasks | 209.08 ms | 78.12 ms |

Table results are the median of seven runs and include saving the active index, reading schedules, refreshing the table, and processing paint events. Timer reset reproduces the old paused-worker freeze. Both interfaces now share one timer. Course totals arrive from the background writer, so timer controls do not wait for a statistics read on the GUI thread.

Reproduce from the repository root:

```powershell
python -m unittest discover -s tests -v
python tests/benchmark_performance.py --baseline 5f439ef
python tests/render_ui.py
```

The 106 regression checks cover delayed ticks, pause/resume fractions, slow persistence, all four cycles, selecting cycle 4 and its long break, early breaks preserving unfinished focus, rapid course/cycle changes, shutdown/reopening, separate break accounting, partial sessions, no duplicate global totals, legacy lecture totals, period/course/lecture filters, midnight attribution, undated historical time, empty evaluations, long chart ranges, setup/settings, prompt save/copy/reset/cancel, data discovery, and table updates. Selecting dots never credits completed Pomodoros. Switching Basic/Expert preserves the same running session. Hiding in either mode preserves that session and worker; Close app stops the worker, saves course time, and quits.

Visual review covers 21 isolated sample screens, including Basic at 440 × 570 and 400 × 520, Expert at 1160 × 820 and 980 × 720, idle/paused/break states, optional lecture selection, empty/full Trends, course filtering, minimum chart size, setup, settings, library, and prompt editing. The review caught and corrected timer controls below Expert's viewport and clipped chart labels at the minimum Trends size. Small Basic windows scroll when expanded lecture details need more room.

Additional CRUD checks cover course/lecture rename, removal, restoration, duplicate-name validation, removal preserving history and course totals, protected active sessions, stale progress callbacks, atomic metadata rollback, daily/weekly schedule CRUD, task completion preservation, active positions after task moves/deletion, cancellation, and write failures. The Manage dialog is reviewed with active and removed items.

Tracking-path checks cover quick Basic/Expert switching without resetting the session, persistent checkbox choice, failed preference saves, no schedule completion before the full focus countdown, course accounting, saved partial sessions when changing paths, stable task identity across routine/day changes and edits/reordering, deleted tasks, queued completion during path changes, early breaks, manual completion during focus, and the final task/break transition. Expert course and schedule layouts are inspected at minimum size, including a completed task turning green.

The Windows build is a directory bundle at `dist/Decipline/Decipline.exe`; keep the full folder together. It includes Python and Qt. Studying, course records, and Trends work offline. Plotting libraries are no longer required. Startup extraction is removed by construction; startup duration has not been benchmarked. Everyday desktop use remains useful feedback beyond offscreen checks.

`Decipline.exe --smoke-test` uses temporary data, constructs the main window and all Trends ranges, selects cycle 4, records a completed course/lecture Pomodoro, acknowledges the completion popup to start its break, checks attribution, edits a prompt, saves setup, and exits normally. Sound and tray notifications are suppressed for the smoke check. It can run beside a real instance without changing its data.

Notification regressions verify that focus completion waits for OK, a hidden window returns with the popup, closing the popup leaves the break stopped, resetting dismisses stale popups, cycle 4 starts its long break, and only a naturally finished break sends Telegram. These tests mock Telegram; no live bot messages are sent.

A previous packaged launch check caught an incompatible ICU library collected from an unrelated SDK on PATH. The build specification excludes that DLL so Qt uses the Windows ICU API.

Telegram setup checks cover the built-in guide, private chat discovery without consuming updates, multiple-recipient protection, missing/invalid tokens, friendly errors without secret URLs, background requests, stale responses, accurate test outcomes, masked tokens, and explicit saving. No live Telegram messages are sent by these tests. The frozen smoke check also opens the setup guide.
