# Vocab Tabs Design

**Date:** 2026-07-09  
**Status:** Approved

## Goal

Replace the single vocabulary list with 3 fixed tabs (1, 2, 3) so the user can group words by context (e.g., YouTube, study, work).

## Data Structure

### Config — before
```json
"vocab": ["GitHub", "Claude Code", "Prompt AI"]
```

### Config — after
```json
"vocab_tabs": {
  "1": ["GitHub", "Claude Code", "Prompt AI"],
  "2": [],
  "3": []
}
```

### Migration
On load: if `vocab` key exists → move its list to `vocab_tabs["1"]`, remove `vocab` key, save config.

### Python state
```python
self._vocab_tabs: dict[str, list[str]]  # {"1": [...], "2": [...], "3": [...]}
self._active_tab: str                   # "1", "2", or "3" — persisted in config
```

## UI

### Header (replaces old label + add button)
```
[ 1 ] [ 2 ] [ 3 ]                   + เพิ่มคำ
```
- Active tab: `fg_color=C['accent']`, `text_color='#fff'`
- Inactive tab: `fg_color=C['card']`, `text_color=C['sub']`
- Width per tab button: 36px, height: 26px

### Scroll area
Same `CTkScrollableFrame` as before. Content rebuilt on tab switch via `_refresh_vocab()`.

### Interactions
| Action | Result |
|--------|--------|
| Click tab 1/2/3 | Switch active tab, save to config, refresh scroll |
| Click "+ เพิ่มคำ" | Add word to active tab, save, refresh |
| Click word button | Copy word to clipboard |
| Click 🗑 | Delete word from active tab, save, refresh |

## Files Changed

- `speech_panel.py` — all changes contained here
- `speech_panel_config.json` — schema change (auto-migrated at runtime)

## Out of Scope

- Renaming tabs
- Adding/removing tabs beyond 3
- Reordering words between tabs
