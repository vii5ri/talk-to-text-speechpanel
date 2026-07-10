# Flexible Matching + Dynamic Tabs + Placeholder System Design

**Date:** 2026-07-10
**Status:** Approved

## Goal

Three improvements to the vocab/dictionary system:

1. **Flexible matching** — auto-correction pairs match despite spaces inserted
   by STT and letter-case differences.
2. **Dynamic tabs** — user can add/remove vocab tabs (was fixed at 3).
3. **Placeholder system** — a configurable token word (default `ABC`, family
   `ABC`–`ABC9`) spoken inside a sentence acts as a fill-in-later object:
   one click selects it, clicking a vocab word replaces every occurrence of
   that token in the clicked card.

## Feature 1: Flexible matching

`_apply_pairs` switches from literal `str.replace` to regex matching:

- Pattern built from the stored `wrong` word with spaces stripped, allowing
  `\s*` between every character, `re.IGNORECASE`.
  - Stored `123` matches `123`, `1 2 3`, `12 3`.
  - Stored `ABC` matches `abc`, `A B C`, `Abc`.
  - Stored `คลอดโค้ด` matches `คลอด โค้ด`.
- Replacement keeps existing rules: Latin `right` is space-padded, double
  spaces collapsed, edges stripped. Longest `wrong` still applies first.
- Requires `import re` (new stdlib import).

## Feature 2: Dynamic tabs

- Tab row becomes `[1] [2] … [N] [+] [–]`, rebuilt dynamically.
- **+** appends a new empty tab named `str(N+1)` and switches to it.
- **–** deletes the *active* tab after `messagebox.askyesno` confirmation that
  states the word count (e.g. "ลบ tab 2 พร้อมคำ 5 คำ?").
  - Refused (toast) when only 1 tab remains.
  - After deletion keys are renumbered contiguously `1..N`; active tab moves
    to the previous tab (or `1`).
- Config schema unchanged (`vocab_tabs: dict[str, list[dict]]`) — only the
  fixed-3 assumption is removed. `vocab_active_tab` clamped to an existing key
  at load.
- Auto-correction still uses pairs from **all** tabs.

## Feature 3: Placeholder system

### Setting

- Config key `placeholder`, default `"ABC"`.
- Vocab panel header gains a small button `📌 ABC`; clicking it opens a
  one-field dialog to change the base word (e.g. to `กขค`). Empty input keeps
  the old value.
- Family recognized automatically: base word alone plus base+single digit
  (`ABC`, `ABC2` … `ABC9`), compared case-insensitively.

### Interaction

1. User dictates the token inside a sentence: "เรียน ABC ขอเชิญ ABC2 และ ABC2".
2. Single click on a token inside a card:
   - The whole token is detected via word boundaries at the click position.
   - All occurrences of that token in the card are highlighted.
   - Hint label shows `📌 จะแทนที่ ABC2 (2 จุด) — คลิกคำใน vocab`.
   - The normal click-copies-card behavior still runs (unchanged).
3. Clicking a vocab word while a token is armed replaces **every occurrence of
   that token in that card only** (other cards untouched), respecting the
   Latin space-padding rule, then clears the highlight/hint. Toast confirms.
   - `ABC` never matches the prefix of `ABC2` (token match requires no digit
     following).
4. Other tokens (`ABC`, `ABC3`) stay until replaced the same way.
5. Manual drag-selection in a card + vocab click replaces just that selection
   (single spot).
6. No token armed and no selection → vocab click copies, exactly as today.

### Disarm rules

- Replaced → cleared.
- Clicking another token → re-arms to the new token.
- Card deleted while armed → pending replacement silently dropped.

## Files Changed

- `speech_panel.py` — all changes contained here.
- `speech_panel_config.json` — new `placeholder` key; tabs may exceed 3.

## Out of Scope

- Multiple independent placeholder base words at the same time.
- Replace-all across every card on screen.
- Renaming tabs (names stay auto-numbered).
