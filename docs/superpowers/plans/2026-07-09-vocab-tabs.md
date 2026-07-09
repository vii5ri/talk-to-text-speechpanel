# Vocab Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single vocabulary list with 3 fixed tabs (1, 2, 3), each holding its own word list, persisted in config.

**Architecture:** All changes are in `speech_panel.py`. The data layer changes from a flat `list[str]` to a `dict[str, list[str]]` keyed by tab number. Existing words migrate to tab "1" automatically at load time. The UI replaces the static label with 3 tab buttons; a `_switch_tab()` method updates the active tab and refreshes the scroll frame.

**Tech Stack:** Python, CustomTkinter, JSON config

## Global Constraints

- No new dependencies
- All 3 tab names are fixed: "1", "2", "3"
- Config key `vocab` (old) → `vocab_tabs` (new), migrated at runtime
- Active tab persisted in config as `vocab_active_tab`

---

### Task 1: Data Layer — replace `_vocab` with `_vocab_tabs`

**Files:**
- Modify: `speech_panel.py` lines ~360–361 (init), ~702–719 (add/delete/save)

**Interfaces:**
- Produces: `self._vocab_tabs: dict[str, list[str]]`, `self._active_tab: str`

- [ ] **Step 1: Replace `_vocab` init with `_vocab_tabs` and migration**

In `__init__`, find:
```python
# Vocabulary (custom word corrections)
self._vocab: list[str] = self._cfg.get('vocab', [])
```

Replace with:
```python
# Vocabulary tabs (migrate old flat list → tab "1")
if 'vocab' in self._cfg and 'vocab_tabs' not in self._cfg:
    self._cfg['vocab_tabs'] = {'1': self._cfg.pop('vocab'), '2': [], '3': []}
    _save_cfg(self._cfg)
self._vocab_tabs: dict[str, list[str]] = self._cfg.get(
    'vocab_tabs', {'1': [], '2': [], '3': []})
self._active_tab: str = self._cfg.get('vocab_active_tab', '1')
```

- [ ] **Step 2: Update `_prompt_add_vocab` to use active tab**

Find:
```python
def _prompt_add_vocab(self):
    dialog = ctk.CTkInputDialog(text='พิมพ์คำที่ต้องการเพิ่ม:', title='เพิ่มคำศัพท์')
    word = dialog.get_input()
    if word and word.strip():
        w = word.strip()
        if w not in self._vocab:
            self._vocab.append(w)
            self._cfg['vocab'] = self._vocab
            _save_cfg(self._cfg)
            self._refresh_vocab()
            self.show_toast(f'เพิ่ม "{w}" แล้ว')
```

Replace with:
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

- [ ] **Step 3: Update `_delete_vocab` to use active tab**

Find:
```python
def _delete_vocab(self, word):
    if word in self._vocab:
        self._vocab.remove(word)
        self._cfg['vocab'] = self._vocab
        _save_cfg(self._cfg)
        self._refresh_vocab()
        self.show_toast(f'ลบ "{word}" แล้ว', 'info')
```

Replace with:
```python
def _delete_vocab(self, word):
    tab = self._vocab_tabs[self._active_tab]
    if word in tab:
        tab.remove(word)
        self._cfg['vocab_tabs'] = self._vocab_tabs
        _save_cfg(self._cfg)
        self._refresh_vocab()
        self.show_toast(f'ลบ "{word}" แล้ว', 'info')
```

- [ ] **Step 4: Verify manually**

รันโปรแกรม → เพิ่มคำ → ปิดแล้วเปิดใหม่ → คำยังอยู่ → ตรวจ `speech_panel_config.json` มี key `vocab_tabs` ไม่มี key `vocab`

- [ ] **Step 5: Commit**

```bash
git add speech_panel.py
git commit -m "feat(vocab): migrate data layer to vocab_tabs dict"
```

---

### Task 2: UI — replace label with tab buttons

**Files:**
- Modify: `speech_panel.py` — `_build_vocab_panel()` และ `_refresh_vocab()`

**Interfaces:**
- Consumes: `self._vocab_tabs`, `self._active_tab`
- Produces: `self._tab_btns: dict[str, CTkButton]`, `_switch_tab(tab: str)`

- [ ] **Step 1: Add `_switch_tab` method (after `_build_vocab_panel`)**

เพิ่มต่อจาก `_build_vocab_panel`:
```python
def _switch_tab(self, tab: str):
    self._active_tab = tab
    self._cfg['vocab_active_tab'] = tab
    _save_cfg(self._cfg)
    for t, btn in self._tab_btns.items():
        if t == tab:
            btn.configure(fg_color=C['accent'], text_color='#fff')
        else:
            btn.configure(fg_color=C['card'], text_color=C['sub'])
    self._refresh_vocab()
```

- [ ] **Step 2: Rewrite `_build_vocab_panel` header**

Find:
```python
def _build_vocab_panel(self, parent):
    vf = ctk.CTkFrame(parent, fg_color=C['card'], corner_radius=8,
                      border_width=1, border_color=C['border'])
    vf.pack(fill='x', padx=4, pady=(0, 4))

    hr = ctk.CTkFrame(vf, fg_color='transparent')
    hr.pack(fill='x', padx=6, pady=(5,2))
    ctk.CTkLabel(hr, text='📚 คำศัพท์ — คลิกเพื่อ Copy',
                 font=_f(11,'bold'), text_color=C['accent']).pack(side='left')
    ctk.CTkButton(hr, text='+ เพิ่มคำ', width=76, height=26, font=_f(11),
                  fg_color=C['accent'], hover_color=C['purple'],
                  command=self._prompt_add_vocab).pack(side='right')
```

Replace with:
```python
def _build_vocab_panel(self, parent):
    vf = ctk.CTkFrame(parent, fg_color=C['card'], corner_radius=8,
                      border_width=1, border_color=C['border'])
    vf.pack(fill='x', padx=4, pady=(0, 4))

    hr = ctk.CTkFrame(vf, fg_color='transparent')
    hr.pack(fill='x', padx=6, pady=(5,2))
    self._tab_btns: dict[str, ctk.CTkButton] = {}
    for t in ('1', '2', '3'):
        active = t == self._active_tab
        btn = ctk.CTkButton(
            hr, text=t, width=36, height=26, font=_f(11, 'bold'),
            fg_color=C['accent'] if active else C['card'],
            text_color='#fff' if active else C['sub'],
            hover_color=C['purple'],
            command=lambda tab=t: self._switch_tab(tab))
        btn.pack(side='left', padx=(0, 3))
        self._tab_btns[t] = btn
    ctk.CTkButton(hr, text='+ เพิ่มคำ', width=76, height=26, font=_f(11),
                  fg_color=C['accent'], hover_color=C['purple'],
                  command=self._prompt_add_vocab).pack(side='right')
```

- [ ] **Step 3: Update `_refresh_vocab` to use active tab**

Find:
```python
def _refresh_vocab(self):
    for w in self._vocab_scroll.winfo_children():
        w.destroy()
    if not self._vocab:
        ctk.CTkLabel(self._vocab_scroll,
                     text='ยังไม่มีคำ — กด "+ เพิ่มคำ" เพื่อใส่คำที่ถูกต้อง',
                     font=_f(10), text_color=C['sub']).pack(pady=6)
        return
    for word in self._vocab:
```

Replace with:
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
```

- [ ] **Step 4: Verify manually**

รันโปรแกรม → ตรวจว่าเห็นปุ่ม 1 / 2 / 3 → คลิกสลับ tab → คำใน tab 1 ยังอยู่ → tab 2 และ 3 ว่าง → เพิ่มคำใน tab 2 → switch ไป tab 1 แล้วกลับมา tab 2 ว่างคำยังอยู่ → ปิดเปิดใหม่ → active tab ที่เลือกไว้ยังคงอยู่

- [ ] **Step 5: Commit**

```bash
git add speech_panel.py
git commit -m "feat(vocab): add 3-tab UI with switch and per-tab word lists"
```
