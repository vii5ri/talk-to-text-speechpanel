#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Speech Panel v2 — Thai / English Speech-to-Text
กด Ctrl+Shift+Space เพื่อแสดง/ซ่อน  |  F10 เพื่อเริ่ม/หยุด  |  F9 พูดใส่แอปอื่น
"""
import threading, io, wave, time, json, re
import os, sys, webbrowser
import datetime, traceback, ctypes
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from deep_translator import GoogleTranslator
import pyperclip
import keyboard
try:
    import pystray
    from PIL import Image as _PILImage
except ImportError:
    pystray = None

# Add NVIDIA CUDA DLLs to PATH before importing faster-whisper
try:
    if getattr(sys, 'frozen', False):
        # Frozen .exe: CUDA DLLs are bundled next to the executable
        _app_dir = os.path.dirname(sys.executable)
        os.environ['PATH'] = _app_dir + os.pathsep + os.environ.get('PATH', '')
        try: os.add_dll_directory(_app_dir)
        except Exception: pass
    else:
        # Development: find DLLs from pip-installed nvidia-* packages
        import site as _site
        for _sp in _site.getsitepackages():
            for _pkg in ('cublas', 'cudnn', 'cuda_runtime', 'cuda_nvrtc', 'cusolver', 'cusparse'):
                _d = os.path.join(_sp, 'nvidia', _pkg, 'bin')
                if os.path.isdir(_d) and _d not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = _d + os.pathsep + os.environ['PATH']
                    try: os.add_dll_directory(_d)
                    except Exception: pass
except Exception:
    pass

try:
    from faster_whisper import WhisperModel as _WhisperModel
except ImportError:
    _WhisperModel = None

# ── Whisper ───────────────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE = 'large-v3'   # large-v3 ≈ 3GB VRAM, best Thai quality
_WHISPER_LANG = {'th-TH': 'th', 'en-US': 'en'}

# ── Layout ────────────────────────────────────────────────────────────────────
PANEL_W    = 880
PANEL_H    = 980
LEFT_W     = 520
HOTKEY      = 'ctrl+shift+space'
RECORD_KEY  = 'f10'
DICTATE_KEY = 'f9'
SAMPLERATE = 16000
BLOCKSIZE  = 1024

POLISH_PROMPT = (
    'ปรับข้อความที่ได้จาก Speech-to-Text ดังนี้:\n'
    '1. ลบคำสร้อยที่ไม่มีความหมาย เช่น "เอ่อ" "อ่า" "อืม" "แบบว่า" "คือว่า"\n'
    '2. ถ้าพูดผิดแล้วแก้กลางประโยค ให้เก็บเฉพาะเวอร์ชันสุดท้ายที่ถูกต้อง\n'
    '3. จัดประโยคให้อ่านง่ายขึ้น แต่ห้ามเปลี่ยนความหมายหรือเพิ่มเนื้อหาใหม่\n'
    '4. ตอบเฉพาะข้อความที่ปรับแล้ว ห้ามอธิบายหรือใส่คำนำ\n\n'
    'ข้อความ:\n{text}'
)

IMAGE_TOOL = 'https://image-to-type-helper.lovable.app/'
AI_CHATS   = {
    'ChatGPT':        'https://chat.openai.com/',
    'Gemini':         'https://gemini.google.com/',
    'Claude':         'https://claude.ai/',
    'Perplexity':     'https://www.perplexity.ai/',
    'Grok':           'https://x.com/i/grok',
    'Meta AI':        'https://www.meta.ai/',
    'Manus':          'https://manus.im/',
    'Talk to Text':   'https://talk-to-text-thai.lovable.app/',
    'Image to Text':  IMAGE_TOOL,
}

# ── Config ────────────────────────────────────────────────────────────────────
_BASE = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, 'frozen', False) else __file__))
_CFG       = os.path.join(_BASE, 'speech_panel_config.json')
_ICON_FILE = os.path.join(_BASE, 'speech_panel.ico')
_LOG_FILE  = os.path.join(_BASE, 'speech_panel_crash.log')
VERSION    = '2.0'

# ── Single-instance guard ──────────────────────────────────────────────────────
_MUTEX_NAME = 'SpeechPanel_SingleInstance_v2'
_mutex_handle = None  # keep reference alive for process lifetime

def _ensure_single_instance():
    global _mutex_handle
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        messagebox.showinfo('Speech Panel', 'Speech Panel เปิดอยู่แล้ว\nดูที่ System Tray หรือกด Ctrl+Shift+Space')
        sys.exit(0)

# ── Crash logger ──────────────────────────────────────────────────────────────

def _write_crash_log(exc_type, exc_value, exc_tb):
    ts  = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    entry = f'\n{"="*60}\n[{ts}]\n{msg}\n'
    try:
        with open(_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception:
        pass

def _setup_crash_handler():
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        _write_crash_log(exc_type, exc_value, exc_tb)
        try:
            messagebox.showerror(
                'Speech Panel — พบข้อผิดพลาด',
                f'โปรแกรมปิดตัวเนื่องจาก:\n'
                f'{exc_type.__name__}: {exc_value}\n\n'
                f'บันทึกรายละเอียดไว้ที่:\n{_LOG_FILE}')
        except Exception:
            pass
    sys.excepthook = _excepthook

def _is_thai(c: str) -> bool:
    return '฀' <= c <= '๿'

def _smart_join(texts: list) -> str:
    """Join segments: no separator between Thai↔Thai boundaries, space otherwise."""
    result = ''
    for t in texts:
        if not t:
            continue
        if result:
            sep = '' if (_is_thai(result[-1]) and _is_thai(t[0])) else ' '
            result += sep + t
        else:
            result = t
    return result

def _fix_punct_spacing(text: str) -> str:
    """Add space after punctuation/special symbols when followed by non-space."""
    # After ? ! … ← sentence-ending marks
    text = re.sub(r'([?!…])([^\s])', r'\1 \2', text)
    # After ๆ ฯ ← Thai special marks
    text = re.sub(r'([ๆฯ])([^\s])', r'\1 \2', text)
    # After , ; ← list/clause separators
    text = re.sub(r'([,;])([^\s])', r'\1 \2', text)
    # After . ← only when NOT a decimal point (skip if digit.digit)
    def _dot(m):
        a, b = m.group(1), m.group(2)
        return m.group(0) if (a.isdigit() and b.isdigit()) else f'{a}. {b}'
    text = re.sub(r'(.)\.([^\s])', _dot, text)
    return text

def _load_cfg() -> dict:
    try:
        with open(_CFG, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cfg(d: dict):
    try:
        with open(_CFG, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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

def _canon_tokens(text: str, base: str) -> str:
    """Normalize spaced placeholder tokens the STT splits apart:
    'A B C 1' / 'ABC 1' / 'abc1' → ' ABC1 ' (canonical, space-separated)."""
    if not base:
        return text
    chars = [c for c in base if c != ' ']
    pat = (r'(?<![A-Za-z])' + r'\s*'.join(re.escape(c) for c in chars)
           + r'\s*(\d)?(?![A-Za-z0-9])')
    def _sub(m):
        return f' {base}{m.group(1) or ""} '
    text = re.sub(pat, _sub, text, flags=re.IGNORECASE)
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text.strip()

# ── Palette ───────────────────────────────────────────────────────────────────
_DARK = dict(bg='#0f172a', header='#1e293b', card='#1e293b', card2='#0f172a',
             combined='#060d17', accent='#3b82f6', purple='#7c3aed',
             red='#ef4444', green='#16a34a', text='#f1f5f9', sub='#64748b',
             border='#334155', del_hover='#7f1d1d')
C = _DARK.copy()
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

def _f(size=15, weight='normal'):
    return ctk.CTkFont(family='Leelawadee UI', size=size, weight=weight)


# ── Toast ─────────────────────────────────────────────────────────────────────
class Toast(ctk.CTkFrame):
    def __init__(self, parent, msg, kind='success'):
        bg = {'success': C['green'], 'error': C['red'], 'info': C['accent']}[kind]
        super().__init__(parent, fg_color=bg, corner_radius=8)
        ctk.CTkLabel(self, text=msg, font=_f(12,'bold'), text_color='#fff').pack(padx=14, pady=6)
        self.place(relx=0.5, rely=0.97, anchor='center')
        self.after(2200, self.destroy)


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


# ── Segment card ──────────────────────────────────────────────────────────────
class SegmentCard(ctk.CTkFrame):
    def __init__(self, parent, text, seg_id, *,
                 on_delete, show_toast, on_change, on_move_up, on_move_down, on_copy,
                 on_polish=None):
        super().__init__(parent, fg_color=C['card'], corner_radius=8,
                         border_width=2, border_color=C['border'])
        self.seg_id      = seg_id
        self._del_cb     = on_delete
        self._toast_cb   = show_toast
        self._change_cb  = on_change
        self._up_cb      = on_move_up
        self._down_cb    = on_move_down
        self._copy_cb    = on_copy
        self._polish_cb  = on_polish
        self.selected    = tk.BooleanVar(value=False)
        self._build(text)

    def _build(self, text):
        top = ctk.CTkFrame(self, fg_color='transparent', height=38)
        top.pack(fill='x', padx=4, pady=(4,0))
        top.pack_propagate(False)

        ctk.CTkCheckBox(top, text='', variable=self.selected, width=18,
                        fg_color=C['accent'], hover_color=C['purple'],
                        checkmark_color='#fff').pack(side='left')
        ctk.CTkLabel(top, text=f'#{self.seg_id}', font=_f(10),
                     text_color=C['sub']).pack(side='left', padx=(3,1))
        ctk.CTkButton(top, text='▲', width=28, height=30, fg_color='transparent',
                      hover_color=C['card2'], font=ctk.CTkFont(size=13),
                      command=lambda: self._up_cb(self)).pack(side='left', padx=1)
        ctk.CTkButton(top, text='▼', width=28, height=30, fg_color='transparent',
                      hover_color=C['card2'], font=ctk.CTkFont(size=13),
                      command=lambda: self._down_cb(self)).pack(side='left', padx=1)

        self._copied_lbl = ctk.CTkLabel(top, text='', font=_f(10,'bold'),
                                         text_color=C['green'], fg_color='transparent')
        self._copied_lbl.pack(side='left', padx=(4,0))

        ctk.CTkButton(top, text='🗑', width=48, height=34, fg_color='transparent',
                      hover_color=C['del_hover'], font=ctk.CTkFont(size=22),
                      command=lambda: self._del_cb(self)).pack(side='right')
        self._polish_btn = ctk.CTkButton(
            top, text='✨', width=38, height=34, fg_color='transparent',
            hover_color=C['purple'], font=ctk.CTkFont(size=18),
            command=self._trigger_polish)
        self._polish_btn.pack(side='right', padx=(0, 2))

        self._tb = ctk.CTkTextbox(self, height=96, font=_f(17),
                                   fg_color=C['card2'], text_color=C['text'],
                                   border_width=0, wrap='word')
        self._tb.pack(fill='x', padx=4, pady=(2,4))
        self._tb.insert('1.0', text)
        try:
            self._tb._textbox.configure(exportselection=False)
        except Exception:
            pass
        self._tb.bind('<Button-1>', lambda e: self._trigger_copy(e))
        self._tb.bind('<KeyRelease>', lambda e: self._fire())
        self._tb.bind('<<Paste>>', lambda e: self.after(20, self._fire))

    def _trigger_copy(self, event=None):
        if self._copy_cb: self._copy_cb(self, event)

    def _trigger_polish(self):
        if self._polish_cb: self._polish_cb(self)

    def _fire(self):
        if self._change_cb: self._change_cb()

    def set_copied(self, active: bool):
        self.configure(border_color=C['green'] if active else C['border'])
        self._copied_lbl.configure(text='✓ คัดลอกแล้ว' if active else '')

    def get_text(self) -> str: return self._tb.get('1.0','end').strip()
    def is_selected(self) -> bool: return self.selected.get()

    def get_selection(self):
        try: return (self._tb.index('sel.first'), self._tb.index('sel.last'))
        except tk.TclError: return None

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

    def replace_at(self, start, end, new_text):
        self._tb.delete(start, end); self._tb.insert(start, new_text); self._fire()


# ── Main window ───────────────────────────────────────────────────────────────
class SpeechPanel(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._cfg          = _load_cfg()
        self._visible      = True
        self._recording    = False
        self._rec_start    = 0.0
        self._audio_chunks = []
        self._stream       = None
        self._lang         = 'th-TH'
        self._recognizer   = sr.Recognizer()
        self._cards: list[SegmentCard] = []
        self._seg_id       = 0
        self._replace_card = None
        self._replace_sel  = None
        self._upd_after    = None
        self._active_card  = None
        self._f9_target    = None   # hwnd to paste into (F9 mode), or None
        self._ph_pending   = None   # (card, token) armed for replacement
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
        if self._active_tab not in self._vocab_tabs:
            self._active_tab = '1'
        self._snap_edge       = 'left'
        self._edge_tab        = None
        self._edge_tab_hover  = None
        self._edge_tab_locked = self._cfg.get('locked', True)   # default: locked (🔒 red)
        self._auto_collapse   = self._cfg.get('auto_collapse', False)
        self._auto_expand     = self._cfg.get('auto_expand', True)   # edge-tab hover → expand
        self._leave_job       = None
        self._gemini_key      = self._cfg.get('gemini_api_key', '')

        self._init_window()
        self._build_ui()
        # Sync button colours and start polling if auto-collapse was saved in config
        self._update_auto_expand_btn()
        if self._auto_collapse and not self._edge_tab_locked:
            self.after(300, self._monitor_leave)   # small delay for window to finish rendering
        keyboard.add_hotkey(HOTKEY, lambda: self.after(0, self._toggle_visibility))
        keyboard.add_hotkey(RECORD_KEY, lambda: self.after(0, self._toggle_rec))
        keyboard.add_hotkey(DICTATE_KEY, lambda: self.after(0, self._f9_toggle))
        self._init_tray()
        self._whisper = None
        if _WhisperModel:
            threading.Thread(target=self._load_whisper, daemon=True).start()

    # ── Window ────────────────────────────────────────────────────────────────

    def _init_window(self):
        self.title(f'Speech Panel v{VERSION}')
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(fg_color=C['bg'])
        self.resizable(False, False)
        sh = self.winfo_screenheight()
        self.geometry(f'{PANEL_W}x{PANEL_H}+0+{max(0,(sh-PANEL_H)//2)}')
        self.protocol('WM_DELETE_WINDOW', self._quit_app)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=C['header'], height=58, corner_radius=0)
        hdr.pack(fill='x'); hdr.pack_propagate(False)
        hdr.bind('<Button-1>', self._drag_start)
        hdr.bind('<B1-Motion>', self._drag_move)
        hdr.bind('<ButtonRelease-1>', self._drag_end)

        ctk.CTkLabel(hdr, text='🎤  Speech Panel',
                     font=_f(14,'bold'), text_color=C['text']).pack(side='left', padx=12)
        # Lock button — controls auto-collapse; 🔒 red=locked (no auto-collapse), 🔓 blue=unlocked
        self._lock_btn = ctk.CTkButton(
            hdr,
            text='🔒' if self._edge_tab_locked else '🔓',
            width=42, height=40,
            fg_color=C['red'] if self._edge_tab_locked else C['accent'],
            hover_color=C['purple'],
            font=ctk.CTkFont(size=16),
            command=self._toggle_lock)
        self._lock_btn.pack(side='left', padx=(0, 2))
        # Auto-expand button — controls edge-tab hover expansion; ⇄ blue=auto-expand, red=manual only
        self._auto_col_btn = ctk.CTkButton(
            hdr, text='⇄', width=42, height=40,
            fg_color=C['accent'] if self._auto_expand else C['red'],
            hover_color=C['purple'],
            font=ctk.CTkFont(size=16), text_color='#fff',
            command=self._toggle_auto_expand)
        self._auto_col_btn.pack(side='left', padx=(0, 6))
        # 4 snap-direction buttons
        self._snap_btns = {}
        _sf = ctk.CTkFrame(hdr, fg_color='transparent')
        _sf.pack(side='left', padx=(0, 4))
        for _d, _s in [('left','◀'), ('top','▲'), ('right','▶'), ('bottom','▼')]:
            _active = _d == self._snap_edge
            _b = ctk.CTkButton(
                _sf, text=_s, width=30, height=36,
                fg_color=C['accent'] if _active else 'transparent',
                hover_color=C['purple'],
                font=ctk.CTkFont(size=13),
                text_color='#fff' if _active else C['sub'],
                command=lambda d=_d: self._snap_to_edge(d))
            _b.pack(side='left', padx=1)
            self._snap_btns[_d] = _b
        # Collapse button — color mirrors lock btn; RED=locked, BLUE=unlocked
        self._collapse_btn = ctk.CTkButton(
            hdr, text='⬡', width=54, height=44,
            fg_color=C['red'] if self._edge_tab_locked else C['accent'],
            hover_color=C['border'],
            font=ctk.CTkFont(size=24), text_color='#fff',
            command=self._collapse_panel)
        self._collapse_btn.pack(side='left', padx=(2, 2))
        # Close (quit) button
        ctk.CTkButton(hdr, text='✕', width=50, height=44, fg_color='transparent',
                      hover_color='#b91c1c', font=ctk.CTkFont(size=20), text_color=C['sub'],
                      command=self._quit_app).pack(side='right', padx=(0,6))
        # Minimize/hide button
        ctk.CTkButton(hdr, text='─', width=50, height=44, fg_color='transparent',
                      hover_color=C['card'], font=ctk.CTkFont(size=20), text_color=C['sub'],
                      command=self._toggle_visibility).pack(side='right', padx=(0,2))
        # Gemini API key settings
        ctk.CTkButton(hdr, text='🔑', width=36, height=36, fg_color='transparent',
                      hover_color=C['card'], font=ctk.CTkFont(size=15), text_color=C['sub'],
                      command=self._set_gemini_key).pack(side='right', padx=(0, 2))
        # AI Chat launcher (header)
        ctk.CTkButton(hdr, text='🤖', width=38, height=34,
                      fg_color=C['accent'], hover_color=C['purple'],
                      font=ctk.CTkFont(size=18),
                      command=self._open_ai_chat).pack(side='right', padx=(2, 4), pady=5)
        self._ai_var = tk.StringVar(value='Gemini')
        self._ai_menu = ctk.CTkOptionMenu(
            hdr, variable=self._ai_var,
            values=list(AI_CHATS.keys()),
            width=130, height=34, font=_f(10),
            fg_color=C['card2'], button_color=C['accent'],
            button_hover_color=C['purple'], text_color=C['text'])
        self._ai_menu.pack(side='right', padx=(4, 2), pady=5)
        # STT engine dropdown (left of AI Chat)
        _init_engine = '🌐 Google' if self._cfg.get('stt_engine', 'google') == 'google' else '🤖 Whisper GPU'
        self._engine_menu = ctk.CTkOptionMenu(
            hdr, values=['🌐 Google', '🤖 Whisper GPU'],
            command=self._set_engine,
            width=148, height=34, font=_f(10),
            fg_color=C['card2'], button_color=C['accent'],
            button_hover_color=C['purple'], text_color=C['text'])
        self._engine_menu.set(_init_engine)
        self._engine_menu.pack(side='right', padx=(4, 6), pady=5)

        # Body
        body = ctk.CTkFrame(self, fg_color=C['bg'], corner_radius=0)
        body.pack(fill='both', expand=True)

        # ── LEFT ─────────────────────────────────────────────────────────────
        left = ctk.CTkFrame(body, fg_color=C['bg'], width=LEFT_W, corner_radius=0)
        left.pack(side='left', fill='y', padx=(6,0), pady=6)
        left.pack_propagate(False)

        # Top row: language + mode selector
        tr = ctk.CTkFrame(left, fg_color=C['bg'], height=30)
        tr.pack(fill='x', padx=4, pady=(0,2)); tr.pack_propagate(False)
        self._lang_var = tk.StringVar(value='TH')
        for lbl, val, code in [('🇹🇭 ไทย','TH','th-TH'),('🇺🇸 EN','EN','en-US')]:
            ctk.CTkRadioButton(tr, text=lbl, variable=self._lang_var, value=val,
                               command=lambda c=code: setattr(self,'_lang',c),
                               font=_f(12), fg_color=C['accent']).pack(side='left', padx=(0,10))

        # Mic zone: status LEFT | mic CENTER (fixed) | timer RIGHT
        # Both side columns have equal uniform minsize so mic never shifts
        _side_w = (LEFT_W - 80) // 2 - 12   # ≈ 202 px each side
        mz = ctk.CTkFrame(left, fg_color=C['bg'])
        mz.pack(fill='x', padx=4, pady=(2,0))
        mz.grid_columnconfigure(0, weight=1, minsize=_side_w)  # status  LEFT
        mz.grid_columnconfigure(1, weight=0, minsize=80)       # mic     CENTER (fixed)
        mz.grid_columnconfigure(2, weight=1, minsize=_side_w)  # timer   RIGHT

        # Left: status text + replace hint
        _lf = ctk.CTkFrame(mz, fg_color='transparent')
        _lf.grid(row=0, column=0, sticky='nsew', padx=(0,4), pady=4)
        self._status_lbl = ctk.CTkLabel(_lf, text='กด F10 หรือปุ่มไมค์เพื่อพูด • F9 = พูดใส่แอปอื่น',
                                         font=_f(11), text_color=C['sub'],
                                         wraplength=_side_w - 8, justify='left')
        self._status_lbl.pack(anchor='w', pady=(6,2))
        self._replace_hint = ctk.CTkLabel(_lf, text='', font=_f(10), text_color=C['purple'])
        self._replace_hint.pack(anchor='w')

        # Center: mic button (always at grid center, never moves)
        self._mic_btn = ctk.CTkButton(
            mz, text='🎤', width=72, height=72, font=ctk.CTkFont(size=30),
            fg_color=C['accent'], hover_color=C['purple'],
            corner_radius=36, command=self._toggle_rec)
        self._mic_btn.grid(row=0, column=1, pady=6)

        # Right: recording timer
        _rf = ctk.CTkFrame(mz, fg_color='transparent')
        _rf.grid(row=0, column=2, sticky='nsew', padx=(4,0), pady=4)
        self._timer_lbl = ctk.CTkLabel(_rf, text='', font=_f(16,'bold'), text_color=C['accent'])
        self._timer_lbl.pack(anchor='center', pady=(16,0))

        # Live preview — hidden by default, auto-shows during real-time STT
        self._partial_tb = ctk.CTkTextbox(
            left, height=72, font=_f(15),
            fg_color=C['card2'], text_color=C['accent'],
            border_width=1, border_color=C['border'],
            wrap='word', state='disabled')
        # (not packed initially — appears only when there is live preview text)

        # Action bar
        self._act_bar = ctk.CTkFrame(left, fg_color=C['bg'])
        self._act_bar.pack(fill='x', padx=4, pady=(0,2))
        act = self._act_bar
        ctk.CTkButton(act, text='📋 ทั้งหมด', height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._copy_all).pack(side='left', fill='x', expand=True, padx=(0,2))
        ctk.CTkButton(act, text='📋 Copy ☑', height=26, font=_f(11),
                      fg_color=C['card'], hover_color=C['accent'], text_color=C['text'],
                      command=self._copy_selected).pack(side='left', fill='x', expand=True, padx=(0,2))
        ctk.CTkButton(act, text='🗑', height=48, width=80, font=ctk.CTkFont(size=30),
                      fg_color=C['card'], hover_color='#b91c1c',
                      command=self._clear_all).pack(side='right')



        # Segments
        self._seg_frame = ctk.CTkScrollableFrame(
            left, fg_color=C['bg'], corner_radius=0,
            scrollbar_button_color=C['border'],
            scrollbar_button_hover_color=C['sub'])
        self._seg_frame.pack(fill='both', expand=True, pady=(2,0))
        self._empty_lbl = ctk.CTkLabel(
            self._seg_frame,
            text='ยังไม่มีข้อความ\nกด F10 เพื่อเริ่มพูด',
            font=_f(12), text_color=C['sub'], justify='center')
        self._empty_lbl.pack(pady=30)

        # Divider
        ctk.CTkFrame(body, width=1, fg_color=C['border'], corner_radius=0
                     ).pack(side='left', fill='y', pady=8)

        # ── RIGHT ────────────────────────────────────────────────────────────
        right = ctk.CTkFrame(body, fg_color=C['bg'], corner_radius=0)
        right.pack(side='left', fill='both', expand=True, padx=(0,6), pady=6)

        # Translation section (bottom, fixed)
        ts = ctk.CTkFrame(right, fg_color=C['bg'])
        ts.pack(side='bottom', fill='x')
        ctk.CTkFrame(ts, height=1, fg_color=C['border']).pack(fill='x', padx=4, pady=(0,5))
        tc = ctk.CTkFrame(ts, fg_color=C['bg'])
        tc.pack(fill='x', padx=4, pady=(0,3))
        ctk.CTkLabel(tc, text='🔄 แปลภาษา', font=_f(12,'bold'), text_color=C['text']).pack(side='left')
        self._trans_dir = ctk.CTkSegmentedButton(tc, values=['TH→EN','EN→TH'],
                                                   width=140, height=26, font=_f(11))
        self._trans_dir.set('TH→EN'); self._trans_dir.pack(side='left', padx=6)
        self._trans_btn = ctk.CTkButton(tc, text='แปล', width=54, height=26, font=_f(12),
                                         fg_color=C['accent'], hover_color=C['purple'],
                                         command=self._do_translate)
        self._trans_btn.pack(side='right')

        ctk.CTkLabel(ts, text='📝 คำแปล', font=_f(11), text_color=C['sub']
                     ).pack(anchor='w', padx=4, pady=(0,1))
        self._trans_box = ctk.CTkTextbox(ts, height=120, font=_f(17),
                                          fg_color=C['combined'], text_color=C['text'],
                                          border_width=1, border_color=C['border'],
                                          wrap='word')
        self._trans_box.pack(fill='x', padx=4, pady=(0,3))
        _tb_row = ctk.CTkFrame(ts, fg_color='transparent')
        _tb_row.pack(fill='x', padx=4, pady=(0,5))
        ctk.CTkButton(_tb_row, text='📋 Copy คำแปล', height=28, font=_f(12),
                      fg_color=C['card'], hover_color=C['accent'], text_color=C['text'],
                      command=self._copy_trans).pack(side='left', fill='x', expand=True, padx=(0,2))
        ctk.CTkButton(_tb_row, text='🗑 ล้าง', height=28, font=_f(12),
                      fg_color=C['card'], hover_color=C['del_hover'], text_color=C['text'],
                      command=lambda: self._set_tb(self._trans_box, '')).pack(side='right')

        ctk.CTkFrame(ts, height=1, fg_color=C['border']).pack(fill='x', padx=4, pady=(0,5))
        ctk.CTkLabel(ts, text='🔍 Cross-check (แปลกลับ)', font=_f(12), text_color=C['sub']
                     ).pack(anchor='w', padx=4, pady=(0,1))
        self._cross_box = ctk.CTkTextbox(ts, height=120, font=_f(17),
                                          fg_color=C['combined'], text_color=C['text'],
                                          border_width=1, border_color=C['border'],
                                          wrap='word')
        self._cross_box.pack(fill='x', padx=4, pady=(0,3))
        _cb_row = ctk.CTkFrame(ts, fg_color='transparent')
        _cb_row.pack(fill='x', padx=4, pady=(0,4))
        ctk.CTkButton(_cb_row, text='📋 Copy Cross-check', height=25, font=_f(11),
                      fg_color=C['card'], hover_color=C['accent'], text_color=C['text'],
                      command=self._copy_cross).pack(side='left', fill='x', expand=True, padx=(0,2))
        ctk.CTkButton(_cb_row, text='🗑 ล้าง', height=25, font=_f(11),
                      fg_color=C['card'], hover_color=C['del_hover'], text_color=C['text'],
                      command=lambda: self._set_tb(self._cross_box, '')).pack(side='right')

        # Copy combined button (bottom of combined section)
        ctk.CTkButton(right, text='📋 Copy กล่องรวม', height=28, font=_f(12),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._copy_combined).pack(side='bottom', fill='x', padx=4, pady=(0,4))

        # Vocabulary panel (above combined box)
        self._build_vocab_panel(right)

        # Combined box (fills remaining space)
        ctk.CTkLabel(right, text='📄 กล่องรวมข้อความ',
                     font=_f(13,'bold'), text_color=C['sub']
                     ).pack(side='top', anchor='w', padx=6, pady=(2,2))
        self._combined_tb = ctk.CTkTextbox(right, font=_f(17),
                                            fg_color=C['combined'], text_color=C['text'],
                                            border_width=1, border_color=C['border'],
                                            wrap='word')
        self._combined_tb.pack(side='top', fill='both', expand=True, padx=4, pady=(0,4))

        self._add_resize_grip()

    # ── Vocabulary panel ──────────────────────────────────────────────────────

    def _build_vocab_panel(self, parent):
        vf = ctk.CTkFrame(parent, fg_color=C['card'], corner_radius=8,
                          border_width=1, border_color=C['border'])
        vf.pack(side='top', fill='x', padx=4, pady=(2,4))

        hr = ctk.CTkFrame(vf, fg_color='transparent')
        hr.pack(fill='x', padx=6, pady=(5,2))
        self._tab_row = ctk.CTkFrame(hr, fg_color='transparent')
        self._tab_row.pack(side='left')
        self._rebuild_tabs()
        ctk.CTkButton(hr, text='+ เพิ่มคำ', width=76, height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._prompt_add_vocab).pack(side='right')
        self._ph_btn = ctk.CTkButton(
            hr, text=f"📌 {self._cfg.get('placeholder', 'ABC')}",
            width=64, height=26, font=_f(10),
            fg_color=C['card'], text_color=C['sub'],
            hover_color=C['purple'], command=self._change_placeholder)
        self._ph_btn.pack(side='right', padx=(0, 4))

        self._vocab_scroll = ctk.CTkScrollableFrame(
            vf, fg_color='transparent', height=95,
            scrollbar_button_color=C['border'],
            scrollbar_button_hover_color=C['sub'])
        self._vocab_scroll.pack(fill='x', padx=4, pady=(0,4))
        self._refresh_vocab()

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

    def _delete_vocab(self, entry):
        tab = self._vocab_tabs[self._active_tab]
        if entry in tab:
            tab.remove(entry)
            self._cfg['vocab_tabs'] = self._vocab_tabs
            _save_cfg(self._cfg)
            self._refresh_vocab()
            self.show_toast(f'ลบ "{entry["right"]}" แล้ว', 'info')

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

    # ── Resize grip ───────────────────────────────────────────────────────────

    def _add_resize_grip(self):
        grip = ctk.CTkLabel(self, text='◢', cursor='size_nw_se',
                            font=ctk.CTkFont(size=14), text_color=C['sub'],
                            fg_color='transparent')
        grip.place(relx=1.0, rely=1.0, anchor='se', x=-4, y=-4)
        grip.bind('<Button-1>', self._resize_start)
        grip.bind('<B1-Motion>', self._resize_move)

    def _resize_start(self, e):
        self._rx = e.x_root; self._ry = e.y_root
        self._rw = self.winfo_width(); self._rh = self.winfo_height()

    def _resize_move(self, e):
        nw = max(800, self._rw + (e.x_root - self._rx))
        nh = max(640, self._rh + (e.y_root - self._ry))
        self.geometry(f'{nw}x{nh}')

    # ── Drag ──────────────────────────────────────────────────────────────────

    def _drag_start(self, e): self._ox = e.x_root - self.winfo_x(); self._oy = e.y_root - self.winfo_y()
    def _drag_move(self, e): self.geometry(f'+{e.x_root-self._ox}+{e.y_root-self._oy}')

    def _drag_end(self, e):
        x  = self.winfo_x();  y  = self.winfo_y()
        w  = self.winfo_width();  h = self.winfo_height()
        sw = self.winfo_screenwidth();  sh = self.winfo_screenheight()
        cx, cy   = x + w // 2, y + h // 2
        d_left, d_right  = cx, sw - cx
        d_top,  d_bottom = cy, sh - cy
        min_d = min(d_left, d_right, d_top, d_bottom)
        if min_d == d_left:
            self._snap_edge = 'left';   self.geometry(f'+0+{y}')
        elif min_d == d_right:
            self._snap_edge = 'right';  self.geometry(f'+{sw-w}+{y}')
        elif min_d == d_top:
            self._snap_edge = 'top';    self.geometry(f'+{x}+0')
        else:
            self._snap_edge = 'bottom'; self.geometry(f'+{x}+{sh-h}')
        self._update_snap_btns()

    # ── Visibility ────────────────────────────────────────────────────────────

    def _toggle_visibility(self):
        if self._visible:
            self._visible = False
            self.withdraw()
        else:
            self._destroy_edge_tab()
            self.deiconify(); self.lift()
            self._visible = True
            if self._auto_collapse and not self._edge_tab_locked:
                self._monitor_leave()

    def _update_snap_btns(self):
        for d, btn in self._snap_btns.items():
            active = d == self._snap_edge
            btn.configure(
                fg_color=C['accent'] if active else 'transparent',
                text_color='#fff' if active else C['sub'])

    def _snap_to_edge(self, edge):
        self._snap_edge = edge
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        w  = self.winfo_width();       h  = self.winfo_height()
        positions = {
            'left':   (0,        (sh - h) // 2),
            'right':  (sw - w,   (sh - h) // 2),
            'top':    ((sw - w) // 2, 0),
            'bottom': ((sw - w) // 2, sh - h),
        }
        x, y = positions[edge]
        self.geometry(f'+{x}+{y}')
        self._update_snap_btns()

    def _toggle_lock(self):
        self._edge_tab_locked = not self._edge_tab_locked
        # Lock OFF → auto-collapse ON, Lock ON → auto-collapse OFF
        self._auto_collapse = not self._edge_tab_locked
        self._cfg['locked'] = self._edge_tab_locked
        self._cfg['auto_collapse'] = self._auto_collapse
        _save_cfg(self._cfg)
        self._update_lock_btn()
        if self._auto_collapse and self._visible:
            self._monitor_leave()

    def _update_lock_btn(self):
        if self._edge_tab_locked:
            self._lock_btn.configure(fg_color=C['red'],    text='🔒')
            self._collapse_btn.configure(fg_color=C['red'])
        else:
            self._lock_btn.configure(fg_color=C['accent'], text='🔓')
            self._collapse_btn.configure(fg_color=C['accent'])

    def _toggle_auto_expand(self):
        self._auto_expand = not self._auto_expand
        self._cfg['auto_expand'] = self._auto_expand
        _save_cfg(self._cfg)
        self._update_auto_expand_btn()

    def _update_auto_expand_btn(self):
        if self._auto_expand:
            self._auto_col_btn.configure(fg_color=C['accent'], text_color='#fff')
        else:
            self._auto_col_btn.configure(fg_color=C['red'], text_color='#fff')

    def _monitor_leave(self):
        if self._leave_job:
            try: self.after_cancel(self._leave_job)
            except Exception: pass
            self._leave_job = None
        if not self._auto_collapse or not self._visible or self._edge_tab_locked or self._recording:
            return
        try:
            mx, my = self.winfo_pointerxy()
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            if mx < wx or mx > wx + ww or my < wy or my > wy + wh:
                self._collapse_panel()
                return
        except Exception:
            pass  # coords unavailable — keep polling
        self._leave_job = self.after(200, self._monitor_leave)

    def _collapse_panel(self):
        if self._leave_job:
            try: self.after_cancel(self._leave_job)
            except Exception: pass
            self._leave_job = None
        self._show_edge_tab()
        self._visible = False
        self.withdraw()

    def _expand_panel(self):
        self._destroy_edge_tab()
        self.deiconify(); self.lift()
        self._visible = True
        self._update_lock_btn()
        self._update_auto_expand_btn()
        if self._auto_collapse:
            self._monitor_leave()

    def _destroy_edge_tab(self):
        if self._edge_tab:
            try: self._edge_tab.destroy()
            except Exception: pass
            self._edge_tab = None
        if self._edge_tab_hover:
            try: self._edge_tab_hover.destroy()
            except Exception: pass
            self._edge_tab_hover = None

    def _show_edge_tab(self):
        self._destroy_edge_tab()
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        px = self.winfo_x(); py = self.winfo_y()
        pw = self.winfo_width(); ph = self.winfo_height()
        edge   = self._snap_edge
        arrows = {'left': '▶', 'right': '◀', 'top': '▼', 'bottom': '▲'}
        arrow  = arrows.get(edge, '▶')
        vertical = edge in ('left', 'right')
        if vertical:
            tw, th = 28, 96
        else:
            tw, th = 116, 28
        if edge == 'left':
            tx, ty = 0, max(0, min(py + (ph - th) // 2, sh - th))
        elif edge == 'right':
            tx, ty = sw - tw, max(0, min(py + (ph - th) // 2, sh - th))
        elif edge == 'top':
            tx, ty = max(0, min(px + (pw - tw) // 2, sw - tw)), 0
        else:
            tx, ty = max(0, min(px + (pw - tw) // 2, sw - tw)), sh - th
        tab = tk.Toplevel()
        tab.overrideredirect(True)
        tab.attributes('-topmost', True)
        tab.configure(bg=C['accent'])
        tab.geometry(f'{tw}x{th}+{tx}+{ty}')
        lock_bg   = C['accent'] if self._auto_expand else C['red']
        lock_icon = '🔓' if self._auto_expand else '🔒'
        expand_lbl = tk.Label(tab, text=arrow, bg=C['accent'], fg='white',
                              font=('Leelawadee UI', 13, 'bold'), cursor='hand2')
        lock_lbl   = tk.Label(tab, text=lock_icon, bg=lock_bg, fg='white',
                              font=('Leelawadee UI', 10), cursor='hand2')
        if vertical:
            expand_lbl.pack(fill='both', expand=True, side='top')
            lock_lbl.pack(fill='x', side='bottom', ipady=5)
        else:
            expand_lbl.pack(fill='both', expand=True, side='left')
            lock_lbl.pack(fill='y', side='right', ipadx=7)
        hover_job = [None]
        def _on_enter(e=None):
            if not self._auto_expand:
                return
            if hover_job[0]:
                try: tab.after_cancel(hover_job[0])
                except Exception: pass
            hover_job[0] = tab.after(350, self._expand_panel)
        def _toggle_lock(e=None):
            self._auto_expand = not self._auto_expand
            self._cfg['auto_expand'] = self._auto_expand
            _save_cfg(self._cfg)
            if self._auto_expand:
                lock_lbl.configure(bg=C['accent'], text='🔓')
            else:
                lock_lbl.configure(bg=C['red'], text='🔒')
                if hover_job[0]:
                    try: tab.after_cancel(hover_job[0])
                    except Exception: pass
                    hover_job[0] = None
        expand_lbl.bind('<Button-1>', lambda e: self._expand_panel())
        expand_lbl.bind('<Enter>', _on_enter)
        lock_lbl.bind('<Button-1>', _toggle_lock)
        tab.bind('<Enter>', _on_enter)
        self._edge_tab = tab

        # Invisible extended hover zone — adds ~150px above & below the tab
        # so the user doesn't have to aim precisely at the small visible strip
        _EXTRA = 150
        if vertical:
            hz_x = tx
            hz_y = max(0, ty - _EXTRA)
            hz_w = tw
            hz_h = min(sh, th + 2 * _EXTRA)
        else:
            hz_x = max(0, tx - _EXTRA)
            hz_y = ty
            hz_w = min(sw, tw + 2 * _EXTRA)
            hz_h = th
        hz = tk.Toplevel()
        hz.overrideredirect(True)
        hz.attributes('-topmost', True)
        hz.attributes('-alpha', 0.01)   # nearly invisible but captures mouse events
        hz.configure(bg='#000000')
        hz.geometry(f'{hz_w}x{hz_h}+{hz_x}+{hz_y}')
        hz.bind('<Enter>', _on_enter)
        hz.bind('<Button-1>', lambda e: self._expand_panel())
        self._edge_tab_hover = hz

    def _quit_app(self):
        if getattr(self, '_tray', None):
            try: self._tray.stop()
            except Exception: pass
        self._destroy_edge_tab()
        try: keyboard.unhook_all()
        except Exception: pass
        self.destroy()
        sys.exit(0)

    # ── System tray ───────────────────────────────────────────────────────────

    def _init_tray(self):
        self._tray = None
        if not pystray:
            return
        try:
            img = _PILImage.open(_ICON_FILE)
        except Exception:
            return
        menu = pystray.Menu(
            pystray.MenuItem('แสดง/ซ่อน',
                             lambda: self.after(0, self._toggle_visibility),
                             default=True),
            pystray.MenuItem('วิธีใช้',
                             lambda: self.after(0, self._show_help)),
            pystray.MenuItem('ออกจากโปรแกรม',
                             lambda: self.after(0, self._quit_app)))
        self._tray = pystray.Icon('SpeechPanel', img, 'Speech Panel', menu)
        threading.Thread(target=self._tray.run, daemon=True).start()

    def _show_help(self):
        messagebox.showinfo(
            'Speech Panel — วิธีใช้',
            'Ctrl+Shift+Space   แสดง/ซ่อนหน้าต่าง\n'
            'F10 หรือปุ่มไมค์   เริ่ม/หยุดอัดเสียง (ลงการ์ด)\n'
            'F9    พูดใส่แอปอื่นโดยตรง\n'
            '       กดอีกครั้ง = ข้อความพิมพ์ลงแอปนั้นทันที\n\n'
            'คลิกการ์ด = copy ข้อความทั้งใบ\n'
            'คลิก ABC / ABC2 ในการ์ด = เลือก token\n'
            '       แล้วคลิกคำใน vocab เพื่อแทนที่ทุกจุด\n'
            'ลากคลุมข้อความ + คลิกคำใน vocab = แทนที่จุดนั้น\n'
            '📌 ปุ่มในแผงคำศัพท์ = เปลี่ยนคำ placeholder')

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

    # ── Partial display ───────────────────────────────────────────────────────

    def _set_partial(self, text: str):
        self._partial_tb.configure(state='normal')
        self._partial_tb.delete('1.0','end')
        if text:
            self._partial_tb.insert('1.0', text)
            if not self._partial_tb.winfo_ismapped():
                self._partial_tb.pack(fill='x', padx=4, pady=(0,4),
                                      before=self._act_bar)
        else:
            if self._partial_tb.winfo_ismapped():
                self._partial_tb.pack_forget()
        self._partial_tb.configure(state='disabled')

    # ── Recording (router) ────────────────────────────────────────────────────

    def _toggle_rec(self):
        if self._recording: self._stop_rec()
        else: self._start_rec()

    def _start_rec(self):
        self._replace_card = None; self._replace_sel = None
        for card in self._cards:
            sel = card.get_selection()
            if sel: self._replace_card = card; self._replace_sel = sel; break

        self._recording = True; self._audio_chunks = []; self._rec_start = time.time()
        self._mic_btn.configure(fg_color=C['red'], text='⏹')
        self._set_partial('')

        if self._replace_card:
            self._set_status('🔴 กำลังฟัง — แทนที่ที่เลือก...')
            self._replace_hint.configure(text=f'📌 แทนที่ใน #{self._replace_card.seg_id}')
        else:
            self._set_status('🔴 กำลังฟัง... กด F10 หรือ ⏹ เพื่อหยุด')
        self._tick()
        self._start_free()

    def _stop_rec(self):
        self._stop_free()

    def _common_stop_ui(self):
        self._mic_btn.configure(fg_color=C['accent'], text='🎤')
        self._timer_lbl.configure(text=''); self._replace_hint.configure(text='')
        if self._auto_collapse and self._visible and not self._edge_tab_locked:
            self._monitor_leave()

    def _apply_dictionary(self, text: str) -> str:
        pairs = [(e['wrong'], e['right'])
                 for entries in self._vocab_tabs.values()
                 for e in entries if e.get('wrong')]
        return _apply_pairs(text, pairs) if pairs else text

    def _finish_text(self, text: str):
        if not text:
            self._f9_target = None
            self._set_status('ไม่ได้ยิน'); return
        text = self._apply_dictionary(text)
        text = _fix_punct_spacing(text)
        text = _canon_tokens(text, self._cfg.get('placeholder', 'ABC'))
        if self._f9_target:
            self._paste_to_target(text)
        if self._replace_card and self._replace_sel:
            c, s, e_ = self._replace_card, *self._replace_sel
            def do():
                c.replace_at(s, e_, text)
                self._replace_card = None; self._replace_sel = None
                self._update_combined(); self._set_status(f'✅ แทนที่ใน #{c.seg_id}')
            self.after(0, do)
        else:
            self.after(0, lambda t=text: self._add_segment(t))

    # ── Whisper loader ────────────────────────────────────────────────────────

    def _load_whisper(self):
        try:
            self.after(0, lambda: self._set_status('⏳ กำลังโหลด Whisper model...'))
            self._whisper = _WhisperModel(
                WHISPER_MODEL_SIZE, device='cuda', compute_type='float16')
            self.after(0, lambda: self._set_status(
                'กด F10 หรือปุ่มไมค์เพื่อพูด • F9 = พูดใส่แอปอื่น'))
        except Exception as err:
            self._whisper = None
            self.after(0, lambda: self._set_status(
                'กด F10 หรือปุ่มไมค์เพื่อพูด • F9 = พูดใส่แอปอื่น'))

    def _set_engine(self, val: str):
        engine = 'whisper' if 'Whisper' in val else 'google'
        self._cfg['stt_engine'] = engine
        _save_cfg(self._cfg)
        if engine == 'whisper' and not self._whisper:
            self._set_status('⏳ Whisper กำลังโหลด...')

    # ── Batch STT ─────────────────────────────────────────────────────────────

    def _start_free(self):
        def _cb(indata, frames, t, status):
            if self._recording: self._audio_chunks.append(indata.copy())
        try:
            self._stream = sd.InputStream(samplerate=SAMPLERATE, channels=1,
                                           dtype='int16', blocksize=BLOCKSIZE, callback=_cb)
            self._stream.start()
        except Exception as e: self._rec_err(f'ไมค์: {e}')

    def _stop_free(self):
        self._recording = False
        if self._stream: self._stream.stop(); self._stream.close(); self._stream = None
        self._common_stop_ui()
        self._set_status('⏳ กำลังแปลงเสียง...')
        threading.Thread(target=self._transcribe_free, daemon=True).start()

    def _transcribe_free(self):
        try:
            if not self._audio_chunks:
                self.after(0, lambda: self._set_status('ไม่มีเสียง')); return
            raw = np.concatenate(self._audio_chunks, axis=0)
            use_whisper = (self._cfg.get('stt_engine', 'google') == 'whisper'
                           and self._whisper)
            if use_whisper:
                audio_f32 = raw.flatten().astype(np.float32) / 32768.0
                lang = _WHISPER_LANG.get(self._lang, 'th')
                segments, _ = self._whisper.transcribe(
                    audio_f32, language=lang, beam_size=5,
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500))
                text = ' '.join(seg.text.strip() for seg in segments).strip()
            else:
                buf = io.BytesIO()
                with wave.open(buf, 'wb') as wf:
                    wf.setnchannels(1); wf.setsampwidth(2)
                    wf.setframerate(SAMPLERATE); wf.writeframes(raw.tobytes())
                buf.seek(0)
                with sr.AudioFile(buf) as src: audio = self._recognizer.record(src)
                text = self._recognizer.recognize_google(audio, language=self._lang)
            if text:
                self.after(0, lambda t=text: self._finish_text(t))
            else:
                self.after(0, lambda: self._rec_err('ฟังไม่ได้ยิน'))
        except sr.UnknownValueError: self.after(0, lambda: self._rec_err('ฟังไม่ได้ยิน'))
        except sr.RequestError:      self.after(0, lambda: self._rec_err('ไม่มีอินเทอร์เน็ต'))
        except Exception as e:       self.after(0, lambda err=e: self._rec_err(str(err)[:50]))

    # ── Common ────────────────────────────────────────────────────────────────

    def _tick(self):
        if not self._recording: return
        t = time.time() - self._rec_start
        self._timer_lbl.configure(text=f'⏱ {int(t//60)}:{int(t%60):02d}')
        self.after(500, self._tick)

    def _rec_err(self, msg):
        self._recording = False; self._replace_card = None
        self._f9_target = None
        self._common_stop_ui()
        self._set_status(f'⚠️ {msg}')

    def _set_status(self, msg): self._status_lbl.configure(text=msg)

    # ── Active copy indicator ─────────────────────────────────────────────────

    def _set_active_card(self, card):
        if self._active_card and self._active_card is not card:
            try: self._active_card.set_copied(False)
            except Exception: pass
        self._active_card = card; card.set_copied(True)

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

    # ── Segments ──────────────────────────────────────────────────────────────

    def _add_segment(self, text):
        if self._empty_lbl.winfo_ismapped(): self._empty_lbl.pack_forget()
        self._seg_id += 1
        card = SegmentCard(self._seg_frame, text, self._seg_id,
                           on_delete=self._delete_segment, show_toast=self.show_toast,
                           on_change=self._schedule_update, on_move_up=self._move_up,
                           on_move_down=self._move_down, on_copy=self._card_copy_clicked,
                           on_polish=self._polish_card)
        self._cards.insert(0, card); self._refresh_order()
        if text: pyperclip.copy(text); self._set_active_card(card)
        self._update_combined()
        self._set_status(f'✅ กล่อง #{self._seg_id} — คัดลอกอัตโนมัติแล้ว')

    def _delete_segment(self, card):
        if card is self._active_card: self._active_card = None
        card.pack_forget(); card.destroy(); self._cards.remove(card)
        self._update_combined()
        if not self._cards: self._empty_lbl.pack(pady=30); self._set_status('กด F10 เพื่อเริ่มพูด')

    def _move_up(self, card):
        i = self._cards.index(card)
        if i > 0:
            self._cards[i], self._cards[i-1] = self._cards[i-1], self._cards[i]
            self._refresh_order(); self._update_combined()

    def _move_down(self, card):
        i = self._cards.index(card)
        if i < len(self._cards)-1:
            self._cards[i], self._cards[i+1] = self._cards[i+1], self._cards[i]
            self._refresh_order(); self._update_combined()

    def _refresh_order(self):
        for c in self._cards: c.pack_forget()
        for c in self._cards: c.pack(fill='x', padx=3, pady=2)

    # ── Combined ──────────────────────────────────────────────────────────────

    def _schedule_update(self):
        if self._upd_after: self.after_cancel(self._upd_after)
        self._upd_after = self.after(300, self._update_combined)

    def _update_combined(self):
        texts = [c.get_text() for c in reversed(self._cards) if c.get_text()]
        self._set_tb(self._combined_tb, _smart_join(texts))

    def _set_tb(self, tb, text):
        tb.delete('1.0','end')
        if text: tb.insert('1.0', text)

    def _copy_combined(self):
        t = self._combined_tb.get('1.0','end').strip()
        if t: pyperclip.copy(t); self.show_toast('📋 Copy กล่องรวมแล้ว')
        else: self.show_toast('กล่องรวมว่างอยู่','info')

    # ── Translation ───────────────────────────────────────────────────────────

    def _do_translate(self):
        text = self._combined_tb.get('1.0','end').strip()
        if not text: self.show_toast('กล่องรวมว่าง','info'); return
        d = self._trans_dir.get()
        src, tgt = ('th','en') if d == 'TH→EN' else ('en','th')
        self._trans_btn.configure(text='กำลังแปล...')
        def do():
            try:
                t1 = GoogleTranslator(source=src, target=tgt).translate(text)
                t2 = GoogleTranslator(source=tgt, target=src).translate(t1)
                def upd(): self._set_tb(self._trans_box,t1); self._set_tb(self._cross_box,t2); self._trans_btn.configure(text='แปล')
                self.after(0, upd)
            except Exception: self.after(0, lambda: self._trans_btn.configure(text='แปล ⚠️'))
        threading.Thread(target=do, daemon=True).start()

    def _copy_trans(self):
        t = self._trans_box.get('1.0','end').strip()
        if t: pyperclip.copy(t); self.show_toast('📋 Copy คำแปลแล้ว')

    def _copy_cross(self):
        t = self._cross_box.get('1.0','end').strip()
        if t: pyperclip.copy(t); self.show_toast('📋 Copy Cross-check แล้ว')

    # ── Bulk ──────────────────────────────────────────────────────────────────

    def _copy_all(self):
        texts = [c.get_text() for c in reversed(self._cards) if c.get_text()]
        if texts: pyperclip.copy(_smart_join(texts)); self.show_toast(f'📋 Copy {len(texts)} กล่อง')
        else: self.show_toast('ยังไม่มีข้อความ','info')

    def _copy_selected(self):
        texts = [c.get_text() for c in reversed(self._cards) if c.is_selected() and c.get_text()]
        if texts:
            pyperclip.copy(_smart_join(texts))
            self.show_toast(f'📋 Copy {len(texts)} กล่อง')
            for c in self._cards:
                c.selected.set(False)
        else: self.show_toast('ยังไม่ได้เลือก','info')

    # ── AI Polish ─────────────────────────────────────────────────────────────

    def _set_gemini_key(self):
        current = self._gemini_key
        hint = f'API Key ปัจจุบัน: {"*" * 8 + current[-4:] if len(current) > 4 else "(ยังไม่ตั้งค่า)"}'
        dlg = ctk.CTkInputDialog(
            text=f'{hint}\n\nวาง Groq API Key ใหม่:\n(รับฟรีที่ console.groq.com → API Keys)',
            title='ตั้งค่า Groq API Key')
        key = dlg.get_input()
        if key is None:
            return
        key = key.strip()
        self._gemini_key = key
        self._cfg['gemini_api_key'] = key
        _save_cfg(self._cfg)
        self.show_toast('บันทึก API Key แล้ว' if key else 'ล้าง API Key แล้ว')

    def _polish_card(self, card):
        key = self._gemini_key.strip()
        if not key:
            self.show_toast('กรุณาตั้งค่า Groq API Key ก่อน (กด 🔑)', 'error')
            self._set_gemini_key()
            return
        text = card.get_text()
        if not text:
            return
        card._polish_btn.configure(text='⏳', state='disabled')
        self._set_status('⏳ กำลัง Polish...')

        def _worker():
            try:
                import requests as _req
                url = 'https://api.groq.com/openai/v1/chat/completions'
                headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
                body = {
                    'model': 'llama-3.1-8b-instant',
                    'messages': [{'role': 'user', 'content': POLISH_PROMPT.format(text=text)}],
                    'temperature': 0.3,
                    'max_tokens': 1024,
                }
                r = _req.post(url, json=body, headers=headers, timeout=30)
                if r.status_code == 429:
                    self.after(0, lambda: self._polish_error(
                        card, 'เกิน quota — รอ 1 นาทีแล้วลองใหม่ (free tier 30 req/นาที)'))
                    return
                if r.status_code in (401, 403):
                    self.after(0, lambda: self._polish_error(
                        card, 'API Key ไม่ถูกต้อง — กด 🔑 แล้ววาง Groq Key ใหม่'))
                    return
                r.raise_for_status()
                data = r.json()
                polished = data['choices'][0]['message']['content'].strip()
                if polished:
                    self.after(0, lambda: self._apply_polish(card, polished))
                else:
                    self.after(0, lambda: self._polish_error(card, 'ไม่ได้รับผลลัพธ์'))
            except Exception as e:
                self.after(0, lambda err=str(e): self._polish_error(card, err))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_polish(self, card, polished):
        card._tb.delete('1.0', 'end')
        card._tb.insert('1.0', polished)
        card._fire()
        card._polish_btn.configure(text='✨', state='normal')
        pyperclip.copy(polished)
        card.set_copied(True)
        self.after(2000, lambda: card.set_copied(False))
        self._set_status('✨ Polish เสร็จ — คัดลอกแล้ว')

    def _polish_error(self, card, msg):
        card._polish_btn.configure(text='✨', state='normal')
        self.show_toast(f'Gemini: {msg}', 'error')

    def _clear_all(self):
        if not self._cards: return
        count = len(self._cards)
        for c in self._cards[:]: c.destroy()
        self._cards.clear(); self._update_combined()
        self._empty_lbl.pack(pady=30); self._set_status('ล้างแล้ว')
        self.show_toast(f'🗑 ล้างแล้ว {count} กล่อง', 'error')

    # ── AI Chat launcher ──────────────────────────────────────────────────────

    def _open_ai_chat(self):
        url = AI_CHATS.get(self._ai_var.get())
        if url: webbrowser.open(url)

    # ── Toast ─────────────────────────────────────────────────────────────────

    def show_toast(self, msg, kind='success'):
        for w in self.winfo_children():
            if isinstance(w, Toast): w.destroy()
        Toast(self, msg, kind)

    def report_callback_exception(self, exc_type, exc_value, exc_tb):
        """Catch exceptions raised inside tkinter event callbacks."""
        _write_crash_log(exc_type, exc_value, exc_tb)
        try:
            messagebox.showerror(
                'Speech Panel — พบข้อผิดพลาด',
                f'เกิดข้อผิดพลาดใน UI:\n'
                f'{exc_type.__name__}: {exc_value}\n\n'
                f'บันทึกรายละเอียดไว้ที่:\n{_LOG_FILE}')
        except Exception:
            pass

    def run(self): self.mainloop()


if __name__ == '__main__':
    _ensure_single_instance()
    _setup_crash_handler()
    try:
        SpeechPanel().run()
    except Exception:
        _write_crash_log(*sys.exc_info())
        raise
