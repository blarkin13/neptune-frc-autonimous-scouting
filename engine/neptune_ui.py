"""Shared desktop presentation for the Windows and Linux training helpers.

The native Mac app uses the same palette and layout, implemented in AppKit.
"""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

INK = '#071522'
PANEL = '#102437'
PANEL_ALT = '#152c42'
LINE = '#29465d'
TEXT = '#f1f7fc'
MUTED = '#a8bdcf'
ACCENT = '#53d4ed'
ACCENT_TEXT = '#06202a'
GOOD = '#85ddc3'


def apply(root):
    root.configure(background=INK)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('Neptune.TFrame', background=INK)
    style.configure('Card.TFrame', background=PANEL)
    style.configure('Neptune.TLabel', background=INK, foreground=TEXT, font=('Arial', 11))
    style.configure('Muted.TLabel', background=INK, foreground=MUTED, font=('Arial', 10))
    style.configure('Card.TLabel', background=PANEL, foreground=TEXT, font=('Arial', 12))
    style.configure('CardMuted.TLabel', background=PANEL, foreground=MUTED, font=('Arial', 10))
    style.configure('Section.TLabel', background=INK, foreground=MUTED, font=('Arial', 10, 'bold'))
    style.configure('Neptune.TButton', background=ACCENT, foreground=ACCENT_TEXT,
                    borderwidth=0, padding=(14, 9), font=('Arial', 10, 'bold'))
    style.map('Neptune.TButton', background=[('active', '#86e7f6'), ('disabled', PANEL_ALT)],
              foreground=[('disabled', MUTED)])
    style.configure('Subtle.TButton', background=PANEL_ALT, foreground=TEXT,
                    borderwidth=1, bordercolor=LINE, padding=(12, 8), font=('Arial', 10))
    style.map('Subtle.TButton', background=[('active', '#1d3d56'), ('disabled', PANEL)],
              foreground=[('disabled', MUTED)])
    style.configure('Neptune.TCombobox', fieldbackground=PANEL_ALT, background=PANEL_ALT,
                    foreground=TEXT, arrowcolor=ACCENT, padding=6)
    style.map('Neptune.TCombobox', fieldbackground=[('readonly', PANEL_ALT)],
              foreground=[('readonly', TEXT)])
    style.configure('Neptune.Horizontal.TProgressbar', background=ACCENT, troughcolor=PANEL_ALT,
                    borderwidth=0)


def header(parent, *, logo=None, subtitle='LOCAL TRAINING COMPUTER', version=''):
    """Compact brand row; the same information order is used by the Mac app."""
    row = tk.Frame(parent, bg=INK)
    row.pack(fill='x', pady=(0, 17))
    logo_path = Path(logo) if logo else None
    if logo_path and logo_path.is_file():
        try:
            picture = tk.PhotoImage(file=str(logo_path))
            picture = picture.subsample(max(1, (picture.width() + 61) // 62))
            mark = tk.Label(row, image=picture, bg=INK, borderwidth=0)
            mark.image = picture
            mark.pack(side='left', padx=(0, 13))
        except tk.TclError:
            logo_path = None
    if not logo_path or not logo_path.is_file():
        tk.Label(row, text='N', font=('Arial', 26, 'bold'), fg=ACCENT, bg=PANEL,
                 width=2).pack(side='left', padx=(0, 13))
    copy = tk.Frame(row, bg=INK)
    copy.pack(side='left', fill='x', expand=True)
    tk.Label(copy, text='NEPTUNE  /  TRAINING', font=('Arial', 9, 'bold'),
             fg=ACCENT, bg=INK, anchor='w').pack(fill='x')
    tk.Label(copy, text='Training Helper', font=('Arial', 20, 'bold'),
             fg=TEXT, bg=INK, anchor='w').pack(fill='x', pady=(2, 1))
    tk.Label(copy, text=subtitle, font=('Arial', 9), fg=MUTED, bg=INK,
             anchor='w').pack(fill='x')
    if version:
        tk.Label(row, text=version, font=('Arial', 9), fg=MUTED, bg=INK,
                 anchor='e').pack(side='right', padx=(8, 0))
    return row


def card(parent, *, padding=16):
    outer = tk.Frame(parent, bg=LINE, padx=1, pady=1)
    outer.pack(fill='x', pady=(0, 14))
    inner = tk.Frame(outer, bg=PANEL, padx=padding, pady=padding)
    inner.pack(fill='both', expand=True)
    return inner


def status(parent, value, *, detail=None, eyebrow='CONNECTION'):
    inner = card(parent)
    tk.Label(inner, text=eyebrow, font=('Arial', 9, 'bold'), fg=ACCENT,
             bg=PANEL, anchor='w').pack(fill='x')
    tk.Label(inner, textvariable=value, font=('Arial', 14, 'bold'), fg=TEXT,
             bg=PANEL, anchor='w', justify='left', wraplength=500).pack(fill='x', pady=(7, 3))
    if detail is not None:
        tk.Label(inner, text=detail, font=('Arial', 10), fg=MUTED, bg=PANEL,
                 anchor='w', justify='left', wraplength=500).pack(fill='x')
    return inner


def activity(parent):
    ttk.Label(parent, text='ACTIVITY', style='Section.TLabel').pack(anchor='w', pady=(5, 7))
    border = tk.Frame(parent, bg=LINE, padx=1, pady=1)
    border.pack(fill='both', expand=True)
    text = tk.Text(border, height=7, wrap='word', state='disabled', borderwidth=0,
                   highlightthickness=0, bg='#07111c', fg=TEXT, insertbackground=TEXT,
                   font=('Menlo', 10), padx=12, pady=10)
    scroll = ttk.Scrollbar(border, orient='vertical', command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    text.pack(side='left', fill='both', expand=True)
    return text
