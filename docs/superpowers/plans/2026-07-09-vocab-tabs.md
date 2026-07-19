# Vocab Tabs ✅ COMPLETED

**Commits:** `0b6e18f` (data layer) · `baf62ed` (UI)
**What was built:** Replaced single vocab list with 3 fixed tabs (1, 2, 3), each with its own word list persisted in config.

## Key Files

| File | Role |
|---|---|
| `speech_panel.py` | All changes — data layer + UI |
| `speech_panel_config.json` | `vocab_tabs: {1:[...], 2:[...], 3:[...]}` + `vocab_active_tab` |

## Key Decisions

- Config key migrated: `vocab` (flat list) → `vocab_tabs` (dict) at runtime
- Active tab persisted as `vocab_active_tab`
- Tab names are fixed strings: `"1"`, `"2"`, `"3"` (later made dynamic in flex-match plan)
