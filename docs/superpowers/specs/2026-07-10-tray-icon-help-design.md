# System Tray Icon + F9 Help Design

**Date:** 2026-07-10
**Status:** Approved

## Goal

1. A system-tray icon shows SpeechPanel is running (even when the window is
   hidden) and offers show/hide, help, and quit.
2. The F9 direct-dictation feature gets discoverable documentation in-app.

## Feature 1: Tray icon

- Library: `pystray` + `Pillow` (both already installed). Import guarded by
  try/except — if missing, the app runs exactly as today with no tray icon.
- Icon image: existing `speech_panel.ico` (`_ICON_FILE`); if the file is
  missing, skip the tray silently.
- Left click (default menu item): show/hide the panel (same as
  Ctrl+Shift+Space).
- Right-click menu: `แสดง/ซ่อน` | `วิธีใช้` | `ออกจากโปรแกรม`.
- pystray runs in a daemon thread; all callbacks hop to the tk main thread via
  `self.after(0, …)`.
- `_quit_app` stops the tray icon before destroying the window.

## Feature 2: F9 help

- Default status text becomes:
  `กดปุ่มหรือ Space เพื่อพูด • F9 = พูดใส่แอปอื่น`
- New `_show_help()` opens a messagebox listing every hotkey/interaction:
  Ctrl+Shift+Space, Space/mic, F9 (two-press flow), card click = copy,
  placeholder click-replace, drag-select replace, 📌 setting button.
- Reachable from the tray menu `วิธีใช้`.

## Files Changed

- `speech_panel.py` only.

## Out of Scope

- Affiliate side panel (future plan, separate project).
- Balloon/toast notifications from the tray.
