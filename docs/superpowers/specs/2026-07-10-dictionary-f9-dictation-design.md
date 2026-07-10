# Auto-Correction Dictionary + F9 Direct Dictation Design

**Date:** 2026-07-10
**Status:** Approved

## Goal

Two features (inspired by Wispr Flow):

1. **Auto-correction dictionary** — upgrade vocab tabs from copy-only words to
   optional `wrong → right` pairs, applied automatically to every transcription
   result.
2. **F9 direct dictation** — press F9 from any app to record speech; the
   corrected text is pasted at the cursor in that app and also saved as a card.

## Feature 1: Auto-Correction Dictionary

### Data structure

Config — before:
```json
"vocab_tabs": { "1": ["GitHub", "Claude Code"], "2": [], "3": [] }
```

Config — after (each entry becomes an object):
```json
"vocab_tabs": {
  "1": [
    {"wrong": "",         "right": "GitHub"},
    {"wrong": "คลอดโค้ด", "right": "Claude Code"}
  ],
  "2": [], "3": []
}
```

- `wrong` empty string → plain copy-only word (current behavior).
- `wrong` non-empty → auto-replacement pair.

### Migration

On load: any entry that is a plain string is converted to
`{"wrong": "", "right": <string>}` and the config re-saved. Existing words are
never lost. (This follows the same pattern as the earlier `vocab` →
`vocab_tabs` migration.)

### Replacement engine

New method `_apply_dictionary(text: str) -> str`:

1. Collect pairs from **all 3 tabs** (not just the active tab), keeping only
   entries with non-empty `wrong`.
2. Sort by `len(wrong)` descending — longest match first, so a short pair never
   eats the middle of a longer one (e.g. check "คลอดโค้ด" before "คลอด").
3. For each pair, replace every occurrence of `wrong` in the text:
   - If `right` contains any Latin letter (`A-Za-z`), insert it as
     `f' {right} '` (space-padded) so English words don't stick to Thai text.
   - Otherwise insert `right` as-is.
4. Collapse any double spaces produced by padding and strip leading/trailing
   whitespace before returning.

Called from `_finish_text()` — the single funnel every transcription result
flows through — so it applies to normal cards, selection-replace mode, and F9
mode automatically.

### UI changes

**Add dialog** — replace single-field `CTkInputDialog` with a small custom
`CTkToplevel` dialog with two entry fields:

```
คำที่ถอดผิด (เว้นว่างได้):  [ กิจฮับ ]
คำที่ถูกต้อง:               [ GitHub ]
                 [ ยกเลิก ] [ บันทึก ]
```

- Both filled → auto-replacement pair.
- First field empty → plain copy word.
- Second field empty → Save disabled/rejected.

**Row display** in the vocab scroll list:

- Plain word: `GitHub` (unchanged look).
- Pair: `คลอดโค้ด → Claude Code`.
- Clicking any row copies the **right** word (with padding spaces, as today).
- 🗑 deletes the whole row. Tab buttons 1/2/3 unchanged.

## Feature 2: F9 Direct Dictation

### Hotkey

Global hotkey **F9**, registered with `keyboard.add_hotkey` alongside the
existing `Ctrl+Shift+Space`. Toggle style: first press starts, second press
stops. Works even while the panel is hidden.

### Flow

1. **First F9 press:**
   - Capture the current foreground window handle via
     `ctypes.windll.user32.GetForegroundWindow()`, store as the paste target.
   - Start recording through the existing pipeline (`_start_rec`).
   - Panel status shows `🔴 F9 — กำลังฟัง จะพิมพ์ลง [window title]`.
2. **Second F9 press:** stop recording → transcribe (Google STT) →
   `_apply_dictionary()` corrects the text.
3. **Paste:**
   - Save current clipboard contents (`pyperclip.paste()`).
   - `SetForegroundWindow(target)` to restore focus to the target app; short
     delay (~150 ms) for the window to become ready.
   - `pyperclip.copy(text)` then `keyboard.send('ctrl+v')`.
   - Short delay, then restore the saved clipboard contents.
4. **Card:** the same text is always added as a card in SpeechPanel too.

### Edge cases

| Situation | Behavior |
|---|---|
| F9 pressed while a normal recording is active | Ignored + warning toast |
| Mic button / Space pressed during an F9 session | Treated as the second F9 press (stop + paste) |
| Target window closed before paste | Skip paste, still add card, info toast |
| Transcription failed (silence / no internet) | No paste, normal error message, F9 state cleared |
| Foreground window at F9 press is SpeechPanel itself | No paste target stored; behaves like a normal recording (card only) |

### Non-goals (out of scope)

- Auto-stop on silence (explicitly deferred by user).
- Push-to-talk (hold F9) mode.
- Frequency counters on dictionary pairs.
- Renaming/adding tabs beyond the fixed 1/2/3.

## Files Changed

- `speech_panel.py` — all changes contained here.
- `speech_panel_config.json` — schema change, auto-migrated at runtime.

## Technical Notes

- No new dependencies: `ctypes`, `keyboard`, `pyperclip` are already imported.
- Paste uses clipboard + Ctrl+V (not `keyboard.write`) because character-by-
  character typing corrupts Thai vowel/tone marks in many apps.
- `SetForegroundWindow` can be blocked by Windows focus rules; if it fails,
  fall back to skip-paste + card + toast (same as "target closed" case).
