# Auto-Correction Dictionary + F9 Direct Dictation ✅ COMPLETED

**Commits:** `16c599c` (Task 1) · `a3ac707` (Task 2) · `f4a54dd` (Task 3)
**What was built:** Vocab entries become `wrong → right` pairs auto-applied to every transcription; F9 hotkey dictates directly into any focused app window.

## Key Files

| File | Role |
|---|---|
| `speech_panel.py` | `_apply_pairs()`, `_apply_dictionary()`, `AddVocabDialog`, `_f9_toggle()`, `_paste_to_target()` |
| `speech_panel_config.json` | entries now `{"wrong": str, "right": str}` per tab |

## Key Decisions / Constraints

- Paste uses clipboard + Ctrl+V, NOT `keyboard.write` — Thai vowel/tone corruption if using write
- Latin (English) replacements are space-padded: `f' {right} '`; double spaces collapsed; result stripped
- Dictionary pairs from **all 3 tabs** apply, not just active tab
- Entries with empty `wrong` = copy-only words (no replacement)
- Old plain-string entries migrate to `{"wrong": "", "right": word}` automatically
- F9 toggle: press starts recording targeting foreground window, press again stops + pastes
- Card is always saved regardless of F9 mode (paste is bonus, not exclusive)
- Clipboard is restored after paste
