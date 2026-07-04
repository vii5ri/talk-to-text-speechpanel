#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Speech Panel v2 — Thai / English Speech-to-Text
Modes: 🌐 Free | 🔌 Vosk (offline real-time) | ☁️ Google Cloud (real-time)
กด Ctrl+Shift+Space เพื่อแสดง/ซ่อน  |  Space เพื่อเริ่ม/หยุด
"""
import threading, io, wave, time, json, queue as queuelib
import os, sys, winreg, subprocess, webbrowser
import datetime, traceback, ctypes
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from deep_translator import GoogleTranslator
import pyperclip
import keyboard

# ── STT modes ─────────────────────────────────────────────────────────────────
STT_FREE   = 'free'
STT_VOSK   = 'vosk'
STT_GCLOUD = 'gcloud'

# ── Layout ────────────────────────────────────────────────────────────────────
PANEL_W    = 880
PANEL_H    = 980
LEFT_W     = 520
HOTKEY     = 'ctrl+shift+space'
SAMPLERATE = 16000
BLOCKSIZE  = 1024
SEP        = ' '
IMAGE_TOOL = 'https://image-to-type-helper.lovable.app/'
AI_CHATS   = {
    'ChatGPT':    'https://chat.openai.com/',
    'Gemini':     'https://gemini.google.com/',
    'Claude':     'https://claude.ai/',
    'Perplexity': 'https://www.perplexity.ai/',
    'Grok':       'https://x.com/i/grok',
    'Meta AI':    'https://www.meta.ai/',
    'Manus':      'https://manus.im/',
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

# ── Windows helpers ───────────────────────────────────────────────────────────
_RUN_KEY  = r'Software\Microsoft\Windows\CurrentVersion\Run'
_APP_NAME = 'SpeechPanel'

def _startup_get() -> bool:
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(k, _APP_NAME); winreg.CloseKey(k); return True
    except OSError:
        return False

def _startup_set(on: bool):
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if on:
            winreg.SetValueEx(k, _APP_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try: winreg.DeleteValue(k, _APP_NAME)
            except FileNotFoundError: pass
        winreg.CloseKey(k)
    except OSError: pass

def _sm_path() -> str:
    return os.path.join(os.environ.get('APPDATA',''),
                        r'Microsoft\Windows\Start Menu\Programs', 'Speech Panel.lnk')

def _sm_exists() -> bool: return os.path.exists(_sm_path())

def _sm_create():
    t = sys.executable.replace('\\','\\\\')
    p = _sm_path().replace('\\','\\\\')
    icon = _ICON_FILE if os.path.isfile(_ICON_FILE) else t
    icon = icon.replace('\\','\\\\')
    cwd = _BASE.replace('\\','\\\\')
    subprocess.run(['powershell','-NoProfile','-Command',
        f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{p}");'
        f'$s.TargetPath="{t}";'
        f'$s.Arguments="speech_panel.py";'
        f'$s.WorkingDirectory="{cwd}";'
        f'$s.IconLocation="{icon}";'
        '$s.Save()'],
        creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)

def _sm_remove():
    p = _sm_path()
    if os.path.exists(p): os.remove(p)

# ── Lazy imports (optional packages) ─────────────────────────────────────────
_vosk_cache: dict = {}   # model_path → vosk.Model

def _vosk():
    try: import vosk; return vosk
    except ImportError: return None

def _gcloud_speech():
    try: from google.cloud import speech; return speech
    except ImportError: return None

# ── Palette ───────────────────────────────────────────────────────────────────
_DARK = dict(bg='#0f172a', header='#1e293b', card='#1e293b', card2='#0f172a',
             combined='#060d17', accent='#3b82f6', purple='#7c3aed',
             red='#ef4444', green='#16a34a', text='#f1f5f9', sub='#64748b',
             border='#334155', del_hover='#7f1d1d')
_LIGHT = dict(bg='#f8fafc', header='#e2e8f0', card='#ffffff', card2='#f1f5f9',
              combined='#edf2f7', accent='#2563eb', purple='#7c3aed',
              red='#dc2626', green='#15803d', text='#0f172a', sub='#64748b',
              border='#cbd5e1', del_hover='#fee2e2')
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


# ── Settings dialog ───────────────────────────────────────────────────────────
class SettingsDialog(ctk.CTkToplevel):
    def __init__(self, parent, cfg: dict, on_save):
        super().__init__(parent)
        self._cfg    = cfg.copy()
        self._on_save = on_save
        self.title('ตั้งค่า STT')
        self.geometry('520x290')
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.grab_set()
        self._build()

    def _build(self):
        pad = dict(padx=20)

        ctk.CTkLabel(self, text='🔌  Vosk — ออฟไลน์ ฟรี real-time',
                     font=_f(12,'bold'), text_color=C['accent']).pack(anchor='w', **pad, pady=(14,2))
        vr = ctk.CTkFrame(self, fg_color='transparent')
        vr.pack(fill='x', **pad)
        self._vosk_v = tk.StringVar(value=self._cfg.get('vosk_path',''))
        ctk.CTkEntry(vr, textvariable=self._vosk_v, font=_f(11), height=30,
                     placeholder_text='เลือก folder ของ Vosk Thai model').pack(
            side='left', fill='x', expand=True, padx=(0,6))
        ctk.CTkButton(vr, text='เลือก Folder', width=110, height=30, font=_f(11),
                      command=self._brw_vosk).pack(side='right')
        ctk.CTkLabel(self, text='ดาวน์โหลด model: alphacephei.com/vosk/models  → vosk-model-small-th-0.15',
                     font=_f(9), text_color=C['sub']).pack(anchor='w', **pad, pady=(2,10))

        ctk.CTkLabel(self, text='☁️  Google Cloud STT — real-time คุณภาพสูง (60 นาที/เดือน ฟรี)',
                     font=_f(12,'bold'), text_color=C['purple']).pack(anchor='w', **pad, pady=(4,2))
        gr = ctk.CTkFrame(self, fg_color='transparent')
        gr.pack(fill='x', **pad)
        self._gc_v = tk.StringVar(value=self._cfg.get('gcloud_creds',''))
        ctk.CTkEntry(gr, textvariable=self._gc_v, font=_f(11), height=30,
                     placeholder_text='เลือก Service Account JSON file').pack(
            side='left', fill='x', expand=True, padx=(0,6))
        ctk.CTkButton(gr, text='เลือก File', width=110, height=30, font=_f(11),
                      command=self._brw_gc).pack(side='right')
        ctk.CTkLabel(self, text='สร้าง Service Account JSON จาก Google Cloud Console → APIs & Services',
                     font=_f(9), text_color=C['sub']).pack(anchor='w', **pad, pady=(2,14))

        br = ctk.CTkFrame(self, fg_color='transparent')
        br.pack(fill='x', **pad, pady=(0,14))
        ctk.CTkButton(br, text='บันทึก', font=_f(13),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._save).pack(side='right', padx=(6,0))
        ctk.CTkButton(br, text='ยกเลิก', font=_f(13),
                      fg_color=C['card'], hover_color=C['border'],
                      command=self.destroy).pack(side='right')

    def _brw_vosk(self):
        p = filedialog.askdirectory(title='เลือก Vosk Model Folder')
        if p: self._vosk_v.set(p)

    def _brw_gc(self):
        p = filedialog.askopenfilename(title='เลือก Credentials JSON',
                                        filetypes=[('JSON','*.json')])
        if p: self._gc_v.set(p)

    def _save(self):
        self._cfg['vosk_path']    = self._vosk_v.get()
        self._cfg['gcloud_creds'] = self._gc_v.get()
        self._on_save(self._cfg)
        self.destroy()


# ── Segment card ──────────────────────────────────────────────────────────────
class SegmentCard(ctk.CTkFrame):
    def __init__(self, parent, text, seg_id, *,
                 on_delete, show_toast, on_change, on_move_up, on_move_down, on_copy):
        super().__init__(parent, fg_color=C['card'], corner_radius=8,
                         border_width=2, border_color=C['border'])
        self.seg_id     = seg_id
        self._del_cb    = on_delete
        self._toast_cb  = show_toast
        self._change_cb = on_change
        self._up_cb     = on_move_up
        self._down_cb   = on_move_down
        self._copy_cb   = on_copy
        self.selected   = tk.BooleanVar(value=False)
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

        self._tb = ctk.CTkTextbox(self, height=96, font=_f(17),
                                   fg_color=C['card2'], text_color=C['text'],
                                   border_width=0, wrap='word')
        self._tb.pack(fill='x', padx=4, pady=(2,4))
        self._tb.insert('1.0', text)
        try:
            self._tb._textbox.configure(exportselection=False)
        except Exception:
            pass
        self._tb.bind('<Button-1>', lambda e: self._trigger_copy())
        self._tb.bind('<KeyRelease>', lambda e: self._fire())
        self._tb.bind('<<Paste>>', lambda e: self.after(20, self._fire))

    def _trigger_copy(self):
        if self._copy_cb: self._copy_cb(self)

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

    def replace_at(self, start, end, new_text):
        self._tb.delete(start, end); self._tb.insert(start, new_text); self._fire()


# ── Main window ───────────────────────────────────────────────────────────────
class SpeechPanel(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._cfg          = _load_cfg()
        self._mode         = self._cfg.get('mode', STT_FREE)
        self._visible      = True
        self._recording    = False
        self._rec_start    = 0.0
        self._audio_chunks = []
        self._stream       = None
        self._lang         = 'th-TH'
        self._recognizer   = sr.Recognizer()
        self._cards: list[SegmentCard] = []
        self._seg_id       = 0
        self._dark         = True
        self._replace_card = None
        self._replace_sel  = None
        self._upd_after    = None
        self._active_card  = None
        # Vosk state
        self._vosk_rec     = None
        self._vosk_text    = ''
        # Google Cloud state
        self._gc_queue     = None
        self._gc_done      = False
        self._gc_final     = ''
        # Vocabulary (custom word corrections)
        self._vocab: list[str] = self._cfg.get('vocab', [])
        self._snap_edge      = 'left'
        self._edge_tab       = None
        self._edge_tab_locked = False

        self._init_window()
        self._build_ui()
        keyboard.add_hotkey(HOTKEY, lambda: self.after(0, self._toggle_visibility))
        self.bind('<space>', self._space_key)

    # ── Window ────────────────────────────────────────────────────────────────

    def _init_window(self):
        self.title(f'Speech Panel v{VERSION}')
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(fg_color=C['bg'])
        self.resizable(False, False)
        sh = self.winfo_screenheight()
        self.geometry(f'{PANEL_W}x{PANEL_H}+0+{max(0,(sh-PANEL_H)//2)}')

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
        # Lock button — leftmost, before direction buttons
        self._lock_btn = ctk.CTkButton(
            hdr,
            text='🔒' if self._edge_tab_locked else '🔓',
            width=42, height=40,
            fg_color=C['red'] if self._edge_tab_locked else C['accent'],
            hover_color=C['purple'],
            font=ctk.CTkFont(size=16),
            command=self._toggle_lock)
        self._lock_btn.pack(side='left', padx=(0, 6))
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
        # Collapse button — large, prominent icon
        self._collapse_btn = ctk.CTkButton(
            hdr, text='⊟', width=54, height=44,
            fg_color=C['card'], hover_color=C['border'],
            font=ctk.CTkFont(size=24), text_color=C['sub'],
            command=self._collapse_panel)
        self._collapse_btn.pack(side='left', padx=(0, 2))
        # Close (quit) button
        ctk.CTkButton(hdr, text='✕', width=50, height=44, fg_color='transparent',
                      hover_color='#b91c1c', font=ctk.CTkFont(size=20), text_color=C['sub'],
                      command=self._quit_app).pack(side='right', padx=(0,6))
        # Minimize/hide button
        ctk.CTkButton(hdr, text='─', width=50, height=44, fg_color='transparent',
                      hover_color=C['card'], font=ctk.CTkFont(size=20), text_color=C['sub'],
                      command=self._toggle_visibility).pack(side='right', padx=(0,2))
        self._theme_btn = ctk.CTkButton(hdr, text='☀️', width=46, height=44,
                                         fg_color='transparent', hover_color=C['card'],
                                         font=ctk.CTkFont(size=20), command=self._toggle_theme)
        self._theme_btn.pack(side='right', padx=2)
        self._startup_btn = ctk.CTkButton(hdr, text='⚙️', width=46, height=44,
                                           fg_color='transparent', hover_color=C['card'],
                                           font=ctk.CTkFont(size=20), command=self._show_settings)
        self._startup_btn.pack(side='right', padx=2)
        ctk.CTkButton(hdr, text='🖼', width=46, height=44,
                      fg_color='transparent', hover_color=C['card'],
                      font=ctk.CTkFont(size=20),
                      command=lambda: webbrowser.open(IMAGE_TOOL)
                      ).pack(side='right', padx=2)

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

        # STT mode selector
        self._mode_seg = ctk.CTkSegmentedButton(
            tr, values=['🌐 Free','🔌 Vosk','☁️ Cloud'],
            height=24, font=_f(10), command=self._on_mode_change)
        mode_map = {STT_FREE:'🌐 Free', STT_VOSK:'🔌 Vosk', STT_GCLOUD:'☁️ Cloud'}
        self._mode_seg.set(mode_map.get(self._mode,'🌐 Free'))
        self._mode_seg.pack(side='right')

        # Mic zone
        mz = ctk.CTkFrame(left, fg_color=C['bg'])
        mz.pack(fill='x', padx=4, pady=2)
        self._mic_btn = ctk.CTkButton(
            mz, text='🎤', width=72, height=72, font=ctk.CTkFont(size=30),
            fg_color=C['accent'], hover_color=C['purple'],
            corner_radius=36, command=self._toggle_rec)
        self._mic_btn.pack()
        self._status_lbl = ctk.CTkLabel(mz, text='กดปุ่มหรือ Space เพื่อเริ่มพูด',
                                         font=_f(11), text_color=C['sub'])
        self._status_lbl.pack(pady=(3,0))
        self._timer_lbl = ctk.CTkLabel(mz, text='', font=_f(12), text_color=C['accent'])
        self._timer_lbl.pack(pady=(1,0))
        self._replace_hint = ctk.CTkLabel(mz, text='', font=_f(10), text_color=C['purple'])
        self._replace_hint.pack(pady=(0,1))

        # Live preview (disabled - use space for combined box)
        self._partial_tb = ctk.CTkTextbox(
            left, height=1, font=_f(15),
            fg_color=C['card2'], text_color=C['accent'],
            border_width=0, border_color=C['border'],
            wrap='word', state='disabled')
        self._partial_tb.pack(fill='x', padx=4, pady=(0,0))

        # Action bar
        act = ctk.CTkFrame(left, fg_color=C['bg'])
        act.pack(fill='x', padx=4, pady=(0,2))
        ctk.CTkButton(act, text='📋 ทั้งหมด', height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._copy_all).pack(side='left', fill='x', expand=True, padx=(0,2))
        ctk.CTkButton(act, text='📋 ที่เลือก', height=26, font=_f(11),
                      fg_color=C['card'], hover_color=C['accent'], text_color=C['text'],
                      command=self._copy_selected).pack(side='left', fill='x', expand=True, padx=(0,2))
        ctk.CTkButton(act, text='🗑', height=40, width=48, font=ctk.CTkFont(size=22),
                      fg_color=C['card'], hover_color='#b91c1c',
                      command=self._clear_all).pack(side='right')

        # Tools row (Image to Text, Talk to Text)
        tools_row = ctk.CTkFrame(left, fg_color=C['bg'])
        tools_row.pack(fill='x', padx=4, pady=(0, 2))
        ctk.CTkButton(tools_row, text='🖼 Image to Text', height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=lambda: webbrowser.open('https://image-to-type-helper.lovable.app/')
                      ).pack(side='left', fill='x', expand=True, padx=(0, 2))
        ctk.CTkButton(tools_row, text='💬 Talk to Text', height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=lambda: webbrowser.open('https://talk-to-text-thai.lovable.app/')
                      ).pack(side='left', fill='x', expand=True)

        # AI Chat launcher
        ai_row = ctk.CTkFrame(left, fg_color=C['card'], corner_radius=8)
        ai_row.pack(fill='x', padx=4, pady=(2, 4))
        ctk.CTkLabel(ai_row, text='🤖', font=ctk.CTkFont(size=13),
                     text_color=C['accent']).pack(side='left', padx=(8, 2), pady=4)
        self._ai_var = tk.StringVar(value='ChatGPT')
        self._ai_menu = ctk.CTkOptionMenu(
            ai_row, variable=self._ai_var,
            values=list(AI_CHATS.keys()),
            width=140, height=26, font=_f(11),
            fg_color=C['card2'], button_color=C['accent'],
            button_hover_color=C['purple'], text_color=C['text'])
        self._ai_menu.pack(side='left', padx=(0, 4), pady=4)
        ctk.CTkButton(ai_row, text='เปิด', width=50, height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._open_ai_chat).pack(side='left', pady=4)

        # Segments
        self._seg_frame = ctk.CTkScrollableFrame(
            left, fg_color=C['bg'], corner_radius=0,
            scrollbar_button_color=C['border'],
            scrollbar_button_hover_color=C['sub'])
        self._seg_frame.pack(fill='both', expand=True, pady=(2,0))
        self._empty_lbl = ctk.CTkLabel(
            self._seg_frame,
            text='ยังไม่มีข้อความ\nกด Space เพื่อเริ่มพูด',
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
        ctk.CTkLabel(hr, text='📚 คำศัพท์ — คลิกเพื่อ Copy',
                     font=_f(11,'bold'), text_color=C['accent']).pack(side='left')
        ctk.CTkButton(hr, text='+ เพิ่มคำ', width=76, height=26, font=_f(11),
                      fg_color=C['accent'], hover_color=C['purple'],
                      command=self._prompt_add_vocab).pack(side='right')

        self._vocab_scroll = ctk.CTkScrollableFrame(
            vf, fg_color='transparent', height=95,
            scrollbar_button_color=C['border'],
            scrollbar_button_hover_color=C['sub'])
        self._vocab_scroll.pack(fill='x', padx=4, pady=(0,4))
        self._refresh_vocab()

    def _refresh_vocab(self):
        for w in self._vocab_scroll.winfo_children():
            w.destroy()
        if not self._vocab:
            ctk.CTkLabel(self._vocab_scroll,
                         text='ยังไม่มีคำ — กด "+ เพิ่มคำ" เพื่อใส่คำที่ถูกต้อง',
                         font=_f(10), text_color=C['sub']).pack(pady=6)
            return
        for word in self._vocab:
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

    def _delete_vocab(self, word):
        if word in self._vocab:
            self._vocab.remove(word)
            self._cfg['vocab'] = self._vocab
            _save_cfg(self._cfg)
            self._refresh_vocab()
            self.show_toast(f'ลบ "{word}" แล้ว', 'info')

    def _copy_vocab(self, word):
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

    # ── Mode ──────────────────────────────────────────────────────────────────

    def _on_mode_change(self, value):
        m = {v: k for k, v in {'🌐 Free': STT_FREE, '🔌 Vosk': STT_VOSK, '☁️ Cloud': STT_GCLOUD}.items()}
        label_to_key = {'🌐 Free': STT_FREE, '🔌 Vosk': STT_VOSK, '☁️ Cloud': STT_GCLOUD}
        self._mode = label_to_key.get(value, STT_FREE)
        self._cfg['mode'] = self._mode
        _save_cfg(self._cfg)

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
        self._update_lock_btn()

    def _update_lock_btn(self):
        if self._edge_tab_locked:
            self._lock_btn.configure(fg_color=C['red'],    text='🔒')
        else:
            self._lock_btn.configure(fg_color=C['accent'], text='🔓')

    def _collapse_panel(self):
        self._show_edge_tab()
        self._visible = False
        self.withdraw()

    def _expand_panel(self):
        self._destroy_edge_tab()
        self.deiconify(); self.lift()
        self._visible = True
        self._update_lock_btn()

    def _destroy_edge_tab(self):
        if self._edge_tab:
            try: self._edge_tab.destroy()
            except Exception: pass
            self._edge_tab = None

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
        lock_bg   = C['red']    if self._edge_tab_locked else C['accent']
        lock_icon = '🔒' if self._edge_tab_locked else '🔓'
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
            if self._edge_tab_locked:
                return
            if hover_job[0]:
                try: tab.after_cancel(hover_job[0])
                except Exception: pass
            hover_job[0] = tab.after(350, self._expand_panel)
        def _toggle_lock(e=None):
            self._edge_tab_locked = not self._edge_tab_locked
            if self._edge_tab_locked:
                lock_lbl.configure(bg=C['red'], text='🔒')
                if hover_job[0]:
                    try: tab.after_cancel(hover_job[0])
                    except Exception: pass
                    hover_job[0] = None
            else:
                lock_lbl.configure(bg=C['accent'], text='🔓')
        expand_lbl.bind('<Button-1>', lambda e: self._expand_panel())
        expand_lbl.bind('<Enter>', _on_enter)
        lock_lbl.bind('<Button-1>', _toggle_lock)
        tab.bind('<Enter>', _on_enter)
        self._edge_tab = tab

    def _quit_app(self):
        self._destroy_edge_tab()
        try: keyboard.unhook_all()
        except Exception: pass
        self.destroy()

    # ── Settings ──────────────────────────────────────────────────────────────

    def _show_settings(self):
        menu = tk.Menu(self, tearoff=0)
        su = _startup_get()
        menu.add_command(label=f'{"✓  " if su else "     "}เริ่มกับ Windows',
                         command=self._toggle_startup)
        sm = _sm_exists()
        menu.add_command(label=f'{"✓  " if sm else "     "}อยู่ใน Start Menu',
                         command=self._toggle_start_menu)
        menu.add_separator()
        menu.add_command(label='⚙️ ตั้งค่า Vosk / Google Cloud',
                         command=self._open_settings_dialog)
        x = self._startup_btn.winfo_rootx()
        y = self._startup_btn.winfo_rooty() + self._startup_btn.winfo_height()
        menu.tk_popup(x, y)

    def _toggle_startup(self):
        _startup_set(not _startup_get())
        self.show_toast('✅ เริ่มกับ Windows แล้ว' if _startup_get()
                        else '⛔ ยกเลิกเริ่มกับ Windows', 'info')

    def _toggle_start_menu(self):
        if _sm_exists():
            _sm_remove(); self.show_toast('⛔ ลบออกจาก Start Menu แล้ว', 'info')
        else:
            _sm_create()
            self.show_toast('✅ เพิ่มใน Start Menu แล้ว' if _sm_exists()
                            else '⚠️ เพิ่มไม่ได้', 'error')

    def _open_settings_dialog(self):
        SettingsDialog(self, self._cfg, self._on_cfg_saved)

    def _on_cfg_saved(self, new_cfg):
        self._cfg = new_cfg; _save_cfg(new_cfg)
        global _vosk_cache; _vosk_cache.clear()   # reload model on next use

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _toggle_theme(self):
        self._dark = not self._dark
        if self._dark: C.update(_DARK); ctk.set_appearance_mode('dark'); self._theme_btn.configure(text='☀️')
        else: C.update(_LIGHT); ctk.set_appearance_mode('light'); self._theme_btn.configure(text='🌙')

    # ── Space key ─────────────────────────────────────────────────────────────

    def _space_key(self, event):
        if isinstance(self.focus_get(), tk.Text): return
        self._toggle_rec(); return 'break'

    # ── Partial display ───────────────────────────────────────────────────────

    def _set_partial(self, text: str):
        self._partial_tb.configure(state='normal')
        self._partial_tb.delete('1.0','end')
        if text: self._partial_tb.insert('1.0', text)
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
            self._set_status('🔴 กำลังฟัง... กด Space หรือ ⏹ เพื่อหยุด')
        self._tick()

        if self._mode == STT_VOSK: self._start_vosk()
        elif self._mode == STT_GCLOUD: self._start_gcloud()
        else: self._start_free()

    def _stop_rec(self):
        if self._mode == STT_VOSK: self._stop_vosk()
        elif self._mode == STT_GCLOUD: self._stop_gcloud()
        else: self._stop_free()

    def _common_stop_ui(self):
        self._mic_btn.configure(fg_color=C['accent'], text='🎤')
        self._timer_lbl.configure(text=''); self._replace_hint.configure(text='')

    def _finish_text(self, text: str):
        if not text: self._set_status('ไม่ได้ยิน'); return
        if self._replace_card and self._replace_sel:
            c, s, e_ = self._replace_card, *self._replace_sel
            def do():
                c.replace_at(s, e_, text)
                self._replace_card = None; self._replace_sel = None
                self._update_combined(); self._set_status(f'✅ แทนที่ใน #{c.seg_id}')
            self.after(0, do)
        else:
            self.after(0, lambda t=text: self._add_segment(t))

    # ── Free mode (batch Google STT) ──────────────────────────────────────────

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
            if not self._audio_chunks: self.after(0, lambda: self._set_status('ไม่มีเสียง')); return
            raw = np.concatenate(self._audio_chunks, axis=0)
            buf = io.BytesIO()
            with wave.open(buf,'wb') as wf:
                wf.setnchannels(1); wf.setsampwidth(2)
                wf.setframerate(SAMPLERATE); wf.writeframes(raw.tobytes())
            buf.seek(0)
            with sr.AudioFile(buf) as src: audio = self._recognizer.record(src)
            text = self._recognizer.recognize_google(audio, language=self._lang)
            self.after(0, lambda t=text: self._finish_text(t))
        except sr.UnknownValueError: self.after(0, lambda: self._rec_err('ฟังไม่ได้ยิน'))
        except sr.RequestError: self.after(0, lambda: self._rec_err('ไม่มีอินเทอร์เน็ต'))
        except Exception as e: self.after(0, lambda: self._rec_err(str(e)[:50]))

    # ── Vosk mode (offline real-time) ─────────────────────────────────────────

    def _start_vosk(self):
        vosk = _vosk()
        if not vosk:
            self._rec_err('ไม่พบ Vosk — pip install vosk'); return
        mp = self._cfg.get('vosk_path','')
        if not mp or not os.path.isdir(mp):
            self._rec_err('กรุณาตั้งค่า Vosk model ใน ⚙️'); return

        self._set_status('⏳ โหลด Vosk model...')
        if mp not in _vosk_cache:
            try: _vosk_cache[mp] = vosk.Model(mp)
            except Exception as e: self._rec_err(f'Vosk model: {e}'); return

        rec = vosk.KaldiRecognizer(_vosk_cache[mp], SAMPLERATE)
        self._vosk_rec = rec; self._vosk_text = ''
        self._set_status('🔴 Vosk กำลังฟัง... (real-time)')

        def _cb(indata, frames, t, status):
            if not self._recording: return
            data = bytes(indata)
            if rec.AcceptWaveform(data):
                w = json.loads(rec.Result()).get('text','')
                if w: self._vosk_text += (' ' if self._vosk_text else '') + w
                self.after(0, lambda d=self._vosk_text: self._set_partial(d))
            else:
                p = json.loads(rec.PartialResult()).get('partial','')
                display = self._vosk_text + (' ' if self._vosk_text and p else '') + p + ('...' if p else '')
                if display: self.after(0, lambda d=display: self._set_partial(d))

        try:
            self._stream = sd.InputStream(samplerate=SAMPLERATE, channels=1,
                                           dtype='int16', blocksize=BLOCKSIZE, callback=_cb)
            self._stream.start()
        except Exception as e: self._rec_err(f'ไมค์: {e}')

    def _stop_vosk(self):
        self._recording = False
        if self._stream: self._stream.stop(); self._stream.close(); self._stream = None
        final = ''
        if self._vosk_rec:
            final = json.loads(self._vosk_rec.FinalResult()).get('text','')
            if final: self._vosk_text += (' ' if self._vosk_text else '') + final
            self._vosk_rec = None
        self._common_stop_ui()
        self._set_partial('')
        full = self._vosk_text
        self._finish_text(full)

    # ── Google Cloud STT (streaming real-time) ────────────────────────────────

    def _start_gcloud(self):
        speech = _gcloud_speech()
        if not speech: self._rec_err('ไม่พบ google-cloud-speech — pip install google-cloud-speech'); return
        cp = self._cfg.get('gcloud_creds','')
        if not cp or not os.path.isfile(cp): self._rec_err('กรุณาตั้งค่า Google credentials ใน ⚙️'); return

        try: client = speech.SpeechClient.from_service_account_file(cp)
        except Exception as e: self._rec_err(f'Credentials: {e}'); return

        self._gc_queue = queuelib.Queue()
        self._gc_done  = False
        self._gc_final = ''

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLERATE, language_code=self._lang)
        sc = speech.StreamingRecognitionConfig(config=config, interim_results=True)

        def _cb(indata, frames, t, status):
            if self._recording: self._gc_queue.put(bytes(indata))

        def _gen():
            while not self._gc_done:
                try:
                    chunk = self._gc_queue.get(timeout=0.5)
                    if chunk is None: return
                    yield speech.StreamingRecognizeRequest(audio_content=chunk)
                except queuelib.Empty:
                    continue

        def _stream_thr():
            try:
                for resp in client.streaming_recognize(sc, _gen()):
                    for res in resp.results:
                        tr = res.alternatives[0].transcript
                        if res.is_final:
                            self._gc_final += (' ' if self._gc_final else '') + tr
                            self.after(0, lambda d=self._gc_final: self._set_partial(d))
                        else:
                            preview = self._gc_final + (' ' if self._gc_final else '') + tr + '...'
                            self.after(0, lambda d=preview: self._set_partial(d))
            except Exception as e:
                self.after(0, lambda: self._set_status(f'⚠️ {str(e)[:40]}'))

        self._set_status('🔴 Google Cloud กำลังฟัง... (real-time)')
        try:
            self._stream = sd.InputStream(samplerate=SAMPLERATE, channels=1,
                                           dtype='int16', blocksize=BLOCKSIZE, callback=_cb)
            self._stream.start()
            threading.Thread(target=_stream_thr, daemon=True).start()
        except Exception as e: self._rec_err(f'ไมค์: {e}')

    def _stop_gcloud(self):
        self._recording = False; self._gc_done = True
        if self._gc_queue: self._gc_queue.put(None)
        if self._stream: self._stream.stop(); self._stream.close(); self._stream = None
        self._common_stop_ui()
        def _finish():
            time.sleep(0.8)
            text = self._gc_final
            self.after(0, lambda: self._set_partial(''))
            self.after(0, lambda t=text: self._finish_text(t))
        threading.Thread(target=_finish, daemon=True).start()

    # ── Common ────────────────────────────────────────────────────────────────

    def _tick(self):
        if not self._recording: return
        t = time.time() - self._rec_start
        self._timer_lbl.configure(text=f'⏱ {int(t//60)}:{int(t%60):02d}')
        self.after(500, self._tick)

    def _rec_err(self, msg):
        self._recording = False; self._replace_card = None
        self._common_stop_ui()
        self._set_status(f'⚠️ {msg}')

    def _set_status(self, msg): self._status_lbl.configure(text=msg)

    # ── Active copy indicator ─────────────────────────────────────────────────

    def _set_active_card(self, card):
        if self._active_card and self._active_card is not card:
            try: self._active_card.set_copied(False)
            except Exception: pass
        self._active_card = card; card.set_copied(True)

    def _card_copy_clicked(self, card):
        t = card.get_text()
        if t: pyperclip.copy(t); self._set_active_card(card)

    # ── Segments ──────────────────────────────────────────────────────────────

    def _add_segment(self, text):
        if self._empty_lbl.winfo_ismapped(): self._empty_lbl.pack_forget()
        self._seg_id += 1
        card = SegmentCard(self._seg_frame, text, self._seg_id,
                           on_delete=self._delete_segment, show_toast=self.show_toast,
                           on_change=self._schedule_update, on_move_up=self._move_up,
                           on_move_down=self._move_down, on_copy=self._card_copy_clicked)
        self._cards.insert(0, card); self._refresh_order()
        if text: pyperclip.copy(text); self._set_active_card(card)
        self._update_combined()
        self._set_status(f'✅ กล่อง #{self._seg_id} — คัดลอกอัตโนมัติแล้ว')

    def _delete_segment(self, card):
        if card is self._active_card: self._active_card = None
        card.pack_forget(); card.destroy(); self._cards.remove(card)
        self._update_combined()
        if not self._cards: self._empty_lbl.pack(pady=30); self._set_status('กด Space เพื่อเริ่มพูด')

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
        self._set_tb(self._combined_tb, SEP.join(texts))

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
        texts = [c.get_text() for c in self._cards if c.get_text()]
        if texts: pyperclip.copy('\n'.join(texts)); self.show_toast(f'📋 Copy {len(texts)} กล่อง')
        else: self.show_toast('ยังไม่มีข้อความ','info')

    def _copy_selected(self):
        texts = [c.get_text() for c in self._cards if c.is_selected() and c.get_text()]
        if texts: pyperclip.copy('\n'.join(texts)); self.show_toast(f'📋 Copy {len(texts)} กล่อง')
        else: self.show_toast('ยังไม่ได้เลือก','info')

    def _clear_all(self):
        if not self._cards: return
        if messagebox.askyesno('ยืนยัน', f'ล้างทั้งหมด {len(self._cards)} กล่อง?', parent=self):
            for c in self._cards[:]: c.destroy()
            self._cards.clear(); self._update_combined()
            self._empty_lbl.pack(pady=30); self._set_status('ล้างแล้ว')

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
