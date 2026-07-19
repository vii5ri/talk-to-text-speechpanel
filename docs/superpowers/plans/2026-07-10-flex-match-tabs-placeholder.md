# Flexible Matching + Dynamic Tabs + Placeholder ✅ COMPLETED

**Commits:** `0070d35` (Task 1) · `3523f2f` (Task 2) · `fdf51b1` (Task 3) · `2fa6273` (fix: normalize STT-split tokens)
**What was built:** Regex-based dictionary matching (space/case-insensitive), add/remove vocab tabs dynamically, and click-to-arm placeholder token replacement.

## Key Files

| File | Role |
|---|---|
| `speech_panel.py` | `_apply_pairs()` (regex), `_rebuild_tabs()`, `_add_tab()`, `_del_tab()`, placeholder methods |

## Key Decisions / Constraints

- `_apply_pairs` uses regex: spaces inside `wrong` word are optional (`\s*` between chars) + `re.IGNORECASE`
- Longest wrong-word first to prevent short pair eating the middle of a longer one
- Tab deletion renumbers tabs: e.g. delete tab 2 → tabs become 1, 2 (not 1, 3)
- Minimum 1 tab; deletion shows word count in confirm dialog
- Placeholder family = base word alone OR base + one digit (`ABC`, `ABC1`–`ABC9`), case-insensitive
- `ABC` must NOT match the prefix of `ABC2` — guarded by negative lookahead `(?!\d)`
- Click on placeholder in card = arm mode; click vocab word = replace all in that card only
- Placeholder token configurable via 📌 button (default `ABC`), persisted in config as `placeholder`
- Fix `2fa6273`: STT sometimes splits token chars with spaces (`A B C 1`) → `_canon_tokens()` normalizes before apply
