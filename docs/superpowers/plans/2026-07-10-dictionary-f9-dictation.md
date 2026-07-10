# Auto-Correction Dictionary + F9 Direct Dictation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Vocab entries become optional `wrong → right` pairs auto-applied to every transcription, and F9 dictates speech directly into whatever app has focus.

**Architecture:** All changes in `speech_panel.py`. A pure module-level function `_apply_pairs()` does the text replacement (headless-testable); `_finish_text()` — the single funnel for all transcription results — calls it. F9 captures the foreground window via `ctypes` before recording and pastes via clipboard + Ctrl+V after.

**Tech Stack:** Python, CustomTkinter, `keyboard`, `pyperclip`, `ctypes` (all already imported).

## Global Constraints

- No new dependencies.
- Paste must use clipboard + Ctrl+V, never `keyboard.write` (Thai vowel/tone corruption).
- English (Latin) replacements are space-padded: `f' {right} '`; double spaces collapsed; result stripped.
- Dictionary pairs from **all 3 tabs** apply, not just the active tab.
- Entries with empty `wrong` are plain copy-only words (current behavior preserved).
- Old plain-string entries migrate automatically to `{"wrong": "", "right": <word>}` — never lost.
- F9 is a toggle: press starts, press again stops. Spec: `docs/superpowers/specs/2026-07-10-dictionary-f9-dictation-design.md`.

---

### Task 1: Replacement engine + data migration + wiring into `_finish_text`

**Files:**
- Modify: `speech_panel.py` — after `_save_cfg` (~line 100), `__init__` vocab block (~line 215), `_finish_text` (~line 879)

**Interfaces:**
- Produces: module-level `_apply_pairs(text: str, pairs: list[tuple[str, str]]) -> str`; method `_apply_dictionary(self, text: str) -> str`; `self._vocab_tabs: dict[str, list[dict]]` where each entry is `{'wrong': str, 'right': str}`.

- [ ] **Step 1: Add `_apply_pairs` module-level function**

Insert directly after the `_save_cfg` function (before the `# ── Palette ──` comment):

```python
def _apply_pairs(text: str, pairs: list) -> str:
    """Replace (wrong, right) pairs in text. Longest wrong first so a short
    pair never eats the middle of a longer one. Latin replacements get a
    space on each side; double spaces are collapsed, edges stripped."""
    for wrong, right in sorted(pairs, key=lambda p: len(p[0]), reverse=True):
        if not wrong:
            continue
        pad = any('a' <= ch.lower() <= 'z' for ch in right)
        text = text.replace(wrong, f' {right} ' if pad else right)
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text.strip()
```

- [ ] **Step 2: Verify the engine headless**

Run (from the repo root):

```powershell
python -c "from speech_panel import _apply_pairs as f; assert f('เปิดกิจฮับให้หน่อย', [('กิจฮับ','GitHub')]) == 'เปิด GitHub ให้หน่อย'; assert f('รันคลอดโค้ดเลย', [('คลอด','Claude'),('คลอดโค้ด','Claude Code')]) == 'รัน Claude Code เลย'; assert f('สวัดดีครับ', [('สวัดดี','สวัสดี')]) == 'สวัสดีครับ'; assert f('ข้อความปกติ', []) == 'ข้อความปกติ'; print('PASS')"
```

Expected: `PASS`. (Import is safe: the app only launches under `if __name__ == '__main__':`.)

- [ ] **Step 3: Migrate entries in `__init__`**

Find:

```python
        # Vocabulary tabs (migrate old flat list → tab "1")
        if 'vocab' in self._cfg and 'vocab_tabs' not in self._cfg:
            self._cfg['vocab_tabs'] = {'1': self._cfg.pop('vocab'), '2': [], '3': []}
            _save_cfg(self._cfg)
        self._vocab_tabs: dict[str, list[str]] = self._cfg.get(
            'vocab_tabs', {'1': [], '2': [], '3': []})
        self._active_tab: str = self._cfg.get('vocab_active_tab', '1')
```

Replace with:

```python
        # Vocabulary tabs (migrate old flat list → tab "1")
        if 'vocab' in self._cfg and 'vocab_tabs' not in self._cfg:
            self._cfg['vocab_tabs'] = {'1': self._cfg.pop('vocab'), '2': [], '3': []}
            _save_cfg(self._cfg)
        self._vocab_tabs: dict[str, list[dict]] = self._cfg.get(
            'vocab_tabs', {'1': [], '2': [], '3': []})
        # Migrate plain-string entries → {"wrong": "", "right": word}
        migrated = False
        for entries in self._vocab_tabs.values():
            for i, e in enumerate(entries):
                if isinstance(e, str):
                    entries[i] = {'wrong': '', 'right': e}
                    migrated = True
        if migrated:
            self._cfg['vocab_tabs'] = self._vocab_tabs
            _save_cfg(self._cfg)
        self._active_tab: str = self._cfg.get('vocab_active_tab', '1')
```

- [ ] **Step 4: Add `_apply_dictionary` method and wire into `_finish_text`**

Find:

```python
    def _finish_text(self, text: str):
        if not text: self._set_status('ไม่ได้ยิน'); return
```

Replace with:

```python
    def _apply_dictionary(self, text: str) -> str:
        pairs = [(e['wrong'], e['right'])
                 for entries in self._vocab_tabs.values()
                 for e in entries if e.get('wrong')]
        return _apply_pairs(text, pairs) if pairs else text

    def _finish_text(self, text: str):
        if not text: self._set_status('ไม่ได้ยิน'); return
        text = self._apply_dictionary(text)
```

Note: Task 1 leaves the vocab UI reading dict entries incorrectly (rows would show dicts). That is fixed in Task 2 — run the interim verification below, then move straight on.

- [ ] **Step 5: Interim verification (engine only)**

```powershell
python -c "import json; cfg = json.load(open('speech_panel_config.json', encoding='utf-8')); print(json.dumps(cfg.get('vocab_tabs'), ensure_ascii=False)[:200])"
```

Then launch `python speech_panel.py` once and close it, and re-run the command above. Expected: entries changed from `["GitHub", ...]` to `[{"wrong": "", "right": "GitHub"}, ...]`.

- [ ] **Step 6: Commit**

```bash
git add speech_panel.py
git commit -m "feat(dict): replacement engine + entry migration, wired into _finish_text"
```

---

### Task 2: Vocab UI — two-field add dialog + pair-aware rows

**Files:**
- Modify: `speech_panel.py` — new `AddVocabDialog` class before `# ── Segment card ──` (~line 125); `_refresh_vocab`, `_prompt_add_vocab`, `_delete_vocab` (~lines 532–575)

**Interfaces:**
- Consumes: entry dicts `{'wrong': str, 'right': str}` from Task 1.
- Produces: `AddVocabDialog(parent)` with `.result: tuple[str, str] | None`; `_delete_vocab(self, entry: dict)`.

- [ ] **Step 1: Add `AddVocabDialog` class**

Insert directly before the `# ── Segment card ──` comment:

```python
# ── Add-vocab dialog ──────────────────────────────────────────────────────────
class AddVocabDialog(ctk.CTkToplevel):
    """Two fields: wrong word (optional) + right word (required).
    After close, .result is (wrong, right) or None if cancelled."""
    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title('เพิ่มคำศัพท์')
        self.geometry('360x200')
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.grab_set()
        ctk.CTkLabel(self, text='คำที่ถอดผิด (เว้นว่างได้):', font=_f(12)
                     ).pack(anchor='w', padx=16, pady=(12, 2))
        self._wrong_e = ctk.CTkEntry(self, font=_f(13))
        self._wrong_e.pack(fill='x', padx=16)
        ctk.CTkLabel(self, text='คำที่ถูกต้อง:', font=_f(12)
                     ).pack(anchor='w', padx=16, pady=(8, 2))
        self._right_e = ctk.CTkEntry(self, font=_f(13))
        self._right_e.pack(fill='x', padx=16)
        br = ctk.CTkFrame(self, fg_color='transparent')
        br.pack(fill='x', padx=16, pady=12)
        ctk.CTkButton(br, text='บันทึก', width=90, font=_f(12),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._save).pack(side='right', padx=(6, 0))
        ctk.CTkButton(br, text='ยกเลิก', width=90, font=_f(12),
                      fg_color=C['card'], hover_color=C['border'],
                      command=self.destroy).pack(side='right')
        self._right_e.bind('<Return>', lambda e: self._save())
        self._wrong_e.focus_set()

    def _save(self):
        right = self._right_e.get().strip()
        if not right:
            return
        self.result = (self._wrong_e.get().strip(), right)
        self.destroy()
```

- [ ] **Step 2: Rewrite `_prompt_add_vocab`**

Find:

```python
    def _prompt_add_vocab(self):
        dialog = ctk.CTkInputDialog(text='พิมพ์คำที่ต้องการเพิ่ม:', title='เพิ่มคำศัพท์')
        word = dialog.get_input()
        if word and word.strip():
            w = word.strip()
            tab = self._vocab_tabs[self._active_tab]
            if w not in tab:
                tab.append(w)
                self._cfg['vocab_tabs'] = self._vocab_tabs
                _save_cfg(self._cfg)
                self._refresh_vocab()
                self.show_toast(f'เพิ่ม "{w}" แล้ว')
```

Replace with:

```python
    def _prompt_add_vocab(self):
        dlg = AddVocabDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        wrong, right = dlg.result
        tab = self._vocab_tabs[self._active_tab]
        if any(e['wrong'] == wrong and e['right'] == right for e in tab):
            return
        tab.append({'wrong': wrong, 'right': right})
        self._cfg['vocab_tabs'] = self._vocab_tabs
        _save_cfg(self._cfg)
        self._refresh_vocab()
        self.show_toast(f'เพิ่ม "{right}" แล้ว')
```

- [ ] **Step 3: Rewrite `_refresh_vocab` rows and `_delete_vocab`**

Find:

```python
    def _refresh_vocab(self):
        for w in self._vocab_scroll.winfo_children():
            w.destroy()
        words = self._vocab_tabs.get(self._active_tab, [])
        if not words:
            ctk.CTkLabel(self._vocab_scroll,
                         text='ยังไม่มีคำ — กด "+ เพิ่มคำ" เพื่อใส่คำที่ถูกต้อง',
                         font=_f(10), text_color=C['sub']).pack(pady=6)
            return
        for word in words:
            row = ctk.CTkFrame(self._vocab_scroll, fg_color='transparent')
            row.pack(fill='x', pady=1)
            ctk.CTkButton(row, text=word, font=_f(13), anchor='w',
                          fg_color=C['card2'], hover_color=C['accent'],
                          text_color=C['text'],
                          command=lambda w=word: self._copy_vocab(w)
                          ).pack(side='left', fill='x', expand=True, padx=(0,3))
            ctk.CTkButton(row, text='🗑', width=34, height=30,
                          font=ctk.CTkFont(size=15), fg_color='transparent',
                          hover_color=C['del_hover'],
                          command=lambda w=word: self._delete_vocab(w)
                          ).pack(side='right')

    def _delete_vocab(self, word):
        tab = self._vocab_tabs[self._active_tab]
        if word in tab:
            tab.remove(word)
            self._cfg['vocab_tabs'] = self._vocab_tabs
            _save_cfg(self._cfg)
            self._refresh_vocab()
            self.show_toast(f'ลบ "{word}" แล้ว', 'info')
```

Replace with:

```python
    def _refresh_vocab(self):
        for w in self._vocab_scroll.winfo_children():
            w.destroy()
        entries = self._vocab_tabs.get(self._active_tab, [])
        if not entries:
            ctk.CTkLabel(self._vocab_scroll,
                         text='ยังไม่มีคำ — กด "+ เพิ่มคำ" เพื่อใส่คำที่ถูกต้อง',
                         font=_f(10), text_color=C['sub']).pack(pady=6)
            return
        for entry in entries:
            label = (f"{entry['wrong']} → {entry['right']}"
                     if entry['wrong'] else entry['right'])
            row = ctk.CTkFrame(self._vocab_scroll, fg_color='transparent')
            row.pack(fill='x', pady=1)
            ctk.CTkButton(row, text=label, font=_f(13), anchor='w',
                          fg_color=C['card2'], hover_color=C['accent'],
                          text_color=C['text'],
                          command=lambda w=entry['right']: self._copy_vocab(w)
                          ).pack(side='left', fill='x', expand=True, padx=(0,3))
            ctk.CTkButton(row, text='🗑', width=34, height=30,
                          font=ctk.CTkFont(size=15), fg_color='transparent',
                          hover_color=C['del_hover'],
                          command=lambda en=entry: self._delete_vocab(en)
                          ).pack(side='right')

    def _delete_vocab(self, entry):
        tab = self._vocab_tabs[self._active_tab]
        if entry in tab:
            tab.remove(entry)
            self._cfg['vocab_tabs'] = self._vocab_tabs
            _save_cfg(self._cfg)
            self._refresh_vocab()
            self.show_toast(f'ลบ "{entry["right"]}" แล้ว', 'info')
```

(`_copy_vocab` is unchanged — it already copies with padding spaces.)

- [ ] **Step 4: Verify manually**

Run `python speech_panel.py`:
1. Old words show as plain rows (e.g. `GitHub`) — click one → toast "คัดลอก", clipboard has ` GitHub `.
2. "+ เพิ่มคำ" → dialog with 2 fields. Save with both filled → row shows `คำผิด → คำถูก`. Save with first empty → plain row. Save with second empty → nothing happens.
3. 🗑 deletes a row; restart app → change persisted.
4. Record speech containing a configured wrong word → card text shows the corrected, space-padded result.

- [ ] **Step 5: Commit**

```bash
git add speech_panel.py
git commit -m "feat(dict): two-field add dialog + pair-aware vocab rows"
```

---

### Task 3: F9 direct dictation

**Files:**
- Modify: `speech_panel.py` — constants (~line 24), `__init__` (state + hotkey, ~lines 210/238), `_rec_err` (~line 933), `_finish_text`, new methods after `_space_key` (~line 890)

**Interfaces:**
- Consumes: `_apply_dictionary` (Task 1) — already applied inside `_finish_text`, so the paste text is pre-corrected.
- Produces: `self._f9_target: int | None`; methods `_f9_toggle(self)`, `_paste_to_target(self, text: str)`.

- [ ] **Step 1: Add constant**

Find `HOTKEY     = 'ctrl+shift+space'` and add directly below:

```python
DICTATE_KEY = 'f9'
```

- [ ] **Step 2: Add state + hotkey in `__init__`**

Find `self._active_card  = None` and add directly below:

```python
        self._f9_target    = None   # hwnd to paste into (F9 mode), or None
```

Find:

```python
        keyboard.add_hotkey(HOTKEY, lambda: self.after(0, self._toggle_visibility))
```

Add directly below:

```python
        keyboard.add_hotkey(DICTATE_KEY, lambda: self.after(0, self._f9_toggle))
```

- [ ] **Step 3: Add F9 methods**

Insert after `_space_key` (before the `# ── Partial display ──` comment):

```python
    # ── F9 direct dictation ───────────────────────────────────────────────────

    def _f9_toggle(self):
        if self._recording:
            if self._f9_target is None:
                self.show_toast('กำลังอัดโหมดปกติอยู่ — ใช้ F9 ไม่ได้', 'error')
                return
            self._stop_rec()
            return
        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()
        own = u.GetAncestor(self.winfo_id(), 2)   # GA_ROOT
        self._f9_target = hwnd if (hwnd and hwnd != own) else None
        self._start_rec()
        if self._f9_target:
            buf = ctypes.create_unicode_buffer(64)
            u.GetWindowTextW(self._f9_target, buf, 64)
            self._set_status(f'🔴 F9 — กำลังฟัง จะพิมพ์ลง {buf.value or "แอปเป้าหมาย"}')

    def _paste_to_target(self, text: str):
        u = ctypes.windll.user32
        target, self._f9_target = self._f9_target, None
        if not u.IsWindow(target):
            self.show_toast('หน้าต่างเป้าหมายถูกปิดแล้ว — เก็บลงการ์ดอย่างเดียว', 'info')
            return
        def _worker():
            try: old = pyperclip.paste()
            except Exception: old = None
            if u.GetForegroundWindow() != target:
                u.SetForegroundWindow(target)
                time.sleep(0.15)
            if u.GetForegroundWindow() != target:
                self.after(0, lambda: self.show_toast(
                    'สลับไปหน้าต่างเป้าหมายไม่ได้ — เก็บลงการ์ดอย่างเดียว', 'info'))
                return
            pyperclip.copy(text)
            keyboard.send('ctrl+v')
            time.sleep(0.15)
            if old is not None:
                pyperclip.copy(old)
        threading.Thread(target=_worker, daemon=True).start()
```

- [ ] **Step 4: Trigger paste from `_finish_text` and clear state on error**

Find (as updated in Task 1):

```python
    def _finish_text(self, text: str):
        if not text: self._set_status('ไม่ได้ยิน'); return
        text = self._apply_dictionary(text)
```

Replace with:

```python
    def _finish_text(self, text: str):
        if not text:
            self._f9_target = None
            self._set_status('ไม่ได้ยิน'); return
        text = self._apply_dictionary(text)
        if self._f9_target:
            self._paste_to_target(text)
```

(`_paste_to_target` clears `self._f9_target` itself; the card/replace logic below this stays unchanged and runs in both modes, satisfying "always save a card".)

Find `_rec_err`:

```python
    def _rec_err(self, msg):
        self._recording = False; self._replace_card = None
```

Replace with:

```python
    def _rec_err(self, msg):
        self._recording = False; self._replace_card = None
        self._f9_target = None
```

- [ ] **Step 5: Verify manually**

Run `python speech_panel.py`:
1. Focus Notepad → press F9 → panel status shows `🔴 F9 — กำลังฟัง จะพิมพ์ลง Untitled - Notepad` → speak → press F9 → text appears in Notepad at the cursor **and** as a new card.
2. Copy some other text first (Ctrl+C), do an F9 dictation, then Ctrl+V manually → the originally copied text pastes (clipboard restored).
3. Start a normal recording with the mic button, press F9 → toast "กำลังอัดโหมดปกติอยู่ — ใช้ F9 ไม่ได้", recording keeps running.
4. Press F9 with SpeechPanel itself focused → behaves like a normal recording (card only, no paste).
5. F9-record, close Notepad before pressing F9 again... target gone → toast, card still added.
6. Dictation containing a dictionary wrong-word → pasted text is corrected.

- [ ] **Step 6: Commit**

```bash
git add speech_panel.py
git commit -m "feat(f9): direct dictation into focused app via global F9 hotkey"
```
