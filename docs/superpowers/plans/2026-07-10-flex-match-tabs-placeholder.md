# Flexible Matching + Dynamic Tabs + Placeholder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dictionary pairs match despite spaces/case, vocab tabs are add/removable, and a configurable placeholder token (`ABC`…`ABC9`) can be click-replaced card-wide from the vocab list.

**Architecture:** All changes in `speech_panel.py`. `_apply_pairs` switches to regex matching. The tab button row becomes a rebuildable sub-frame with +/– buttons. Placeholder logic lives in the panel: a click in a card detects the token via word boundaries, arms a pending replacement, and `_copy_vocab` consumes it.

**Tech Stack:** Python, CustomTkinter, `re` (stdlib, new import).

## Global Constraints

- No new pip dependencies (`re` is stdlib).
- Latin replacements space-padded, double spaces collapsed (existing rule).
- Minimum 1 tab; deletion requires confirmation with word count.
- Placeholder family = base word alone or base+one digit, case-insensitive; `ABC` must not match the prefix of `ABC2`.
- Replace-all scope: the clicked card only.
- Spec: `docs/superpowers/specs/2026-07-10-flex-match-tabs-placeholder-design.md`.

---

### Task 1: Flexible matching in `_apply_pairs`

**Files:**
- Modify: `speech_panel.py` — imports (~line 8), `_apply_pairs` (~line 103)

**Interfaces:**
- Produces: same signature `_apply_pairs(text: str, pairs: list) -> str`, now space/case-insensitive.

- [ ] **Step 1: Add `re` import**

Change `import threading, io, wave, time, json` to `import threading, io, wave, time, json, re`.

- [ ] **Step 2: Rewrite `_apply_pairs`**

```python
def _apply_pairs(text: str, pairs: list) -> str:
    """Replace (wrong, right) pairs in text. Longest wrong first. Matching
    ignores letter case and any spaces inside the wrong word (STT often
    splits '123' into '1 2 3'). Latin replacements get a space on each
    side; double spaces are collapsed, edges stripped."""
    for wrong, right in sorted(pairs, key=lambda p: len(p[0]), reverse=True):
        if not wrong:
            continue
        chars = [c for c in wrong if c != ' ']
        pat = r'\s*'.join(re.escape(c) for c in chars)
        pad = any('a' <= ch.lower() <= 'z' for ch in right)
        repl = f' {right} ' if pad else right
        text = re.sub(pat, lambda m: repl, text, flags=re.IGNORECASE)
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text.strip()
```

- [ ] **Step 3: Verify headless**

```powershell
python -c "from speech_panel import _apply_pairs as f; assert f('รหัสคือ 1 2 3 ครับ', [('123','โปรเจกต์เอ')]) == 'รหัสคือ โปรเจกต์เอ ครับ'; assert f('พิมพ์ a b c ให้หน่อย', [('ABC','GitHub')]) == 'พิมพ์ GitHub ให้หน่อย'; assert f('เปิดกิจฮับ', [('กิจฮับ','GitHub')]) == 'เปิด GitHub'; assert f('คลอด โค้ด ดีมาก', [('คลอดโค้ด','Claude Code')]) == 'Claude Code ดีมาก'; print('PASS')"
```

Expected: `PASS`

- [ ] **Step 4: Commit**

```bash
git add speech_panel.py
git commit -m "feat(dict): space/case-insensitive matching via regex"
```

---

### Task 2: Dynamic tabs

**Files:**
- Modify: `speech_panel.py` — `__init__` active-tab clamp (~line 246), `_build_vocab_panel` + `_switch_tab` (~lines 557–595)

**Interfaces:**
- Produces: `_rebuild_tabs(self)`, `_add_tab(self)`, `_del_tab(self)`; `self._tab_row: CTkFrame`.

- [ ] **Step 1: Clamp active tab in `__init__`**

Find `self._active_tab: str = self._cfg.get('vocab_active_tab', '1')` and replace with:

```python
        self._active_tab: str = self._cfg.get('vocab_active_tab', '1')
        if self._active_tab not in self._vocab_tabs:
            self._active_tab = '1'
```

- [ ] **Step 2: Rebuildable tab row in `_build_vocab_panel`**

Replace the fixed `for t in ('1', '2', '3')` block:

```python
        hr = ctk.CTkFrame(vf, fg_color='transparent')
        hr.pack(fill='x', padx=6, pady=(5,2))
        self._tab_row = ctk.CTkFrame(hr, fg_color='transparent')
        self._tab_row.pack(side='left')
        self._rebuild_tabs()
        ctk.CTkButton(hr, text='+ เพิ่มคำ', width=76, height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._prompt_add_vocab).pack(side='right')
```

- [ ] **Step 3: Add `_rebuild_tabs`, `_add_tab`, `_del_tab`; update `_switch_tab`**

```python
    def _rebuild_tabs(self):
        for w in self._tab_row.winfo_children():
            w.destroy()
        self._tab_btns: dict[str, ctk.CTkButton] = {}
        for t in sorted(self._vocab_tabs, key=int):
            active = t == self._active_tab
            btn = ctk.CTkButton(
                self._tab_row, text=t, width=36, height=26, font=_f(11, 'bold'),
                fg_color=C['accent'] if active else C['card'],
                text_color='#fff' if active else C['sub'],
                hover_color=C['purple'],
                command=lambda tab=t: self._switch_tab(tab))
            btn.pack(side='left', padx=(0, 3))
            self._tab_btns[t] = btn
        ctk.CTkButton(self._tab_row, text='+', width=26, height=26,
                      font=_f(12, 'bold'), fg_color=C['card'],
                      text_color=C['green'], hover_color=C['purple'],
                      command=self._add_tab).pack(side='left', padx=(2, 1))
        ctk.CTkButton(self._tab_row, text='–', width=26, height=26,
                      font=_f(12, 'bold'), fg_color=C['card'],
                      text_color=C['red'], hover_color=C['del_hover'],
                      command=self._del_tab).pack(side='left')

    def _add_tab(self):
        new = str(len(self._vocab_tabs) + 1)
        self._vocab_tabs[new] = []
        self._cfg['vocab_tabs'] = self._vocab_tabs
        self._active_tab = new
        self._cfg['vocab_active_tab'] = new
        _save_cfg(self._cfg)
        self._rebuild_tabs()
        self._refresh_vocab()

    def _del_tab(self):
        if len(self._vocab_tabs) <= 1:
            self.show_toast('ต้องมีอย่างน้อย 1 tab', 'error')
            return
        n = len(self._vocab_tabs[self._active_tab])
        if not messagebox.askyesno('ลบ tab',
                f'ลบ tab {self._active_tab} พร้อมคำ {n} คำ?'):
            return
        del self._vocab_tabs[self._active_tab]
        keys = sorted(self._vocab_tabs, key=int)
        self._vocab_tabs = {str(i + 1): self._vocab_tabs[k]
                            for i, k in enumerate(keys)}
        self._active_tab = '1'
        self._cfg['vocab_tabs'] = self._vocab_tabs
        self._cfg['vocab_active_tab'] = self._active_tab
        _save_cfg(self._cfg)
        self._rebuild_tabs()
        self._refresh_vocab()
```

Update `_switch_tab` to tolerate rebuilt buttons (unchanged logic works — it only recolors `self._tab_btns`).

- [ ] **Step 4: Verify manually**

Run app: `+` adds tab 4 (empty, becomes active); add a word in tab 4; `–` on tab 4 → confirm dialog shows "พร้อมคำ 1 คำ" → tabs back to 1-3, active = 1; `–` repeatedly until 1 tab → toast refuses. Restart → tabs persisted.

- [ ] **Step 5: Commit**

```bash
git add speech_panel.py
git commit -m "feat(vocab): add/remove tabs dynamically with confirmation"
```

---

### Task 3: Placeholder system

**Files:**
- Modify: `speech_panel.py` — `__init__` state, vocab header (📌 button), `SegmentCard` (click event + highlight/replace helpers), `_card_copy_clicked`, `_copy_vocab`

**Interfaces:**
- Produces: `self._ph_pending: tuple | None` (card, token); `SegmentCard.word_at(event) -> str`, `.highlight_all(token) -> int`, `.clear_highlight()`, `.replace_token(token, repl) -> int`; panel `_is_placeholder(word) -> str | None`, `_change_placeholder()`.

- [ ] **Step 1: State + config in `__init__`**

After `self._f9_target    = None   # hwnd to paste into (F9 mode), or None` add:

```python
        self._ph_pending   = None   # (card, token) armed for replacement
```

- [ ] **Step 2: SegmentCard — pass click event + helpers**

Change `self._tb.bind('<Button-1>', lambda e: self._trigger_copy())` to
`self._tb.bind('<Button-1>', lambda e: self._trigger_copy(e))` and
`def _trigger_copy(self):` / `if self._copy_cb: self._copy_cb(self)` to:

```python
    def _trigger_copy(self, event=None):
        if self._copy_cb: self._copy_cb(self, event)
```

Add methods to `SegmentCard`:

```python
    def word_at(self, event) -> str:
        tb = self._tb._textbox
        idx = tb.index(f'@{event.x},{event.y}')
        try:
            return tb.get(f'{idx} wordstart', f'{idx} wordend').strip()
        except tk.TclError:
            return ''

    def highlight_all(self, token: str) -> int:
        tb = self._tb._textbox
        tb.tag_remove('ph', '1.0', 'end')
        tb.tag_configure('ph', background=C['purple'], foreground='#fff')
        count, pos = 0, '1.0'
        while True:
            pos = tb.search(token, pos, stopindex='end', nocase=True)
            if not pos: break
            end = f'{pos}+{len(token)}c'
            nxt = tb.get(end, f'{end}+1c')
            if not nxt.isdigit():          # ABC must not hit ABC2
                tb.tag_add('ph', pos, end)
                count += 1
            pos = end
        return count

    def clear_highlight(self):
        try: self._tb._textbox.tag_remove('ph', '1.0', 'end')
        except tk.TclError: pass

    def replace_token(self, token: str, repl: str) -> int:
        text = self.get_text()
        pat = re.escape(token) + r'(?!\d)'
        new, n = re.subn(pat, lambda m: repl, text, flags=re.IGNORECASE)
        if n:
            while '  ' in new:
                new = new.replace('  ', ' ')
            self._tb.delete('1.0', 'end')
            self._tb.insert('1.0', new.strip())
            self._fire()
        return n
```

- [ ] **Step 3: Panel — placeholder detection + arming in `_card_copy_clicked`**

Replace:

```python
    def _card_copy_clicked(self, card):
        t = card.get_text()
        if t: pyperclip.copy(t); self._set_active_card(card)
```

with:

```python
    def _is_placeholder(self, word: str):
        base = self._cfg.get('placeholder', 'ABC')
        if not word or not base: return None
        w = word.lower(); b = base.lower()
        if w == b or (w.startswith(b) and len(w) == len(b) + 1
                      and w[-1].isdigit()):
            return word
        return None

    def _card_copy_clicked(self, card, event=None):
        if event is not None:
            token = self._is_placeholder(card.word_at(event))
            if token:
                n = card.highlight_all(token)
                if n:
                    if self._ph_pending and self._ph_pending[0] is not card:
                        self._ph_pending[0].clear_highlight()
                    self._ph_pending = (card, token)
                    self._replace_hint.configure(
                        text=f'📌 จะแทนที่ {token} ({n} จุด) — คลิกคำใน vocab')
                    return
            if self._ph_pending:
                self._ph_pending[0].clear_highlight()
                self._ph_pending = None
                self._replace_hint.configure(text='')
        t = card.get_text()
        if t: pyperclip.copy(t); self._set_active_card(card)
```

- [ ] **Step 4: `_copy_vocab` consumes armed token or manual selection**

Replace:

```python
    def _copy_vocab(self, word):
        pyperclip.copy(f' {word} ')
        self.show_toast(f'📋 คัดลอก "{word}" แล้ว')
```

with:

```python
    def _copy_vocab(self, word):
        pad = any('a' <= ch.lower() <= 'z' for ch in word)
        ins = f' {word} ' if pad else word
        if self._ph_pending:
            card, token = self._ph_pending
            self._ph_pending = None
            self._replace_hint.configure(text='')
            if card in self._cards:
                n = card.replace_token(token, ins)
                card.clear_highlight()
                if n:
                    self._update_combined()
                    self.show_toast(f'แทนที่ {token} ทั้ง {n} จุดด้วย "{word}"')
                    return
        for card in self._cards:
            sel = card.get_selection()
            if sel:
                card.replace_at(sel[0], sel[1], ins)
                self._update_combined()
                self.show_toast(f'แทนที่ข้อความที่เลือกด้วย "{word}"')
                return
        pyperclip.copy(f' {word} ')
        self.show_toast(f'📋 คัดลอก "{word}" แล้ว')
```

- [ ] **Step 5: 📌 setting button in vocab header**

In `_build_vocab_panel`, before the `+ เพิ่มคำ` button add:

```python
        self._ph_btn = ctk.CTkButton(
            hr, text=f"📌 {self._cfg.get('placeholder', 'ABC')}",
            width=64, height=26, font=_f(10),
            fg_color=C['card'], text_color=C['sub'],
            hover_color=C['purple'], command=self._change_placeholder)
        self._ph_btn.pack(side='right', padx=(0, 4))
```

And add the method:

```python
    def _change_placeholder(self):
        dlg = ctk.CTkInputDialog(
            text=f"คำ placeholder ปัจจุบัน: {self._cfg.get('placeholder', 'ABC')}\nพิมพ์คำใหม่:",
            title='ตั้งค่า Placeholder')
        word = dlg.get_input()
        if word and word.strip():
            self._cfg['placeholder'] = word.strip()
            _save_cfg(self._cfg)
            self._ph_btn.configure(text=f"📌 {word.strip()}")
            self.show_toast(f'Placeholder = "{word.strip()}" แล้ว')
```

- [ ] **Step 6: Verify manually**

1. Dictate/paste a card containing `เรียน ABC ขอเชิญ ABC2 และ ABC2` (type into a card directly works too).
2. Click on `ABC2` → both occurrences highlight, hint shows "(2 จุด)".
3. Click a vocab word → both `ABC2` replaced, `ABC` untouched, toast shows.
4. Click `ABC` → 1 จุด → replace works independently.
5. Drag-select arbitrary text, click vocab word → that selection replaced.
6. No selection, no token → vocab click copies (old behavior).
7. 📌 button → change to `กขค` → restart app → button shows `📌 กขค`, tokens `กขค`/`กขค2` now detected.

- [ ] **Step 7: Commit**

```bash
git add speech_panel.py
git commit -m "feat(placeholder): click-to-arm token replacement from vocab"
```
