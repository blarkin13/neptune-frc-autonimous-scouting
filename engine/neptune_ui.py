"""Shared desktop presentation for the Windows and Linux training helpers.

The native Mac app uses the same palette and layout, implemented in AppKit.
"""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

INK = '#12233d'
PANEL = '#172e4c'
PANEL_ALT = '#1f3a5c'
LINE = '#385c80'
LOG = '#0d1a2e'
TEXT = '#f1f7fc'
MUTED = '#a8bdcf'
ACCENT = '#53d4ed'
ACCENT_TEXT = '#06202a'
GOOD = '#85ddc3'
COLLAPSED_SIZE = '600x530'
EXPANDED_SIZE = '600x718'


def apply(root):
    root.configure(background=INK)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('Meter.Horizontal.TProgressbar',background='#8fb6de',troughcolor='#0f1d31',borderwidth=0,thickness=4)
    style.configure('Neptune.TFrame', background=INK)
    style.configure('Card.TFrame', background=PANEL)
    style.configure('Neptune.TLabel', background=INK, foreground=TEXT, font=('Arial', 11))
    style.configure('Muted.TLabel', background=INK, foreground=MUTED, font=('Arial', 10))
    style.configure('Card.TLabel', background=PANEL, foreground=TEXT, font=('Arial', 12))
    style.configure('CardMuted.TLabel', background=PANEL, foreground=MUTED, font=('Arial', 10))
    style.configure('Section.TLabel', background=INK, foreground=MUTED, font=('Arial', 10, 'bold'))
    style.configure('Neptune.TButton', background=ACCENT, foreground=ACCENT_TEXT,
                    borderwidth=0, padding=(12, 7), font=('Arial', 10, 'bold'))
    style.map('Neptune.TButton', background=[('active', '#86e7f6'), ('disabled', PANEL_ALT)],
              foreground=[('disabled', MUTED)])
    style.configure('Subtle.TButton', background=PANEL_ALT, foreground=TEXT,
                    borderwidth=1, bordercolor=LINE, padding=(10, 6), font=('Arial', 10))
    style.map('Subtle.TButton', background=[('active', '#1d3d56'), ('disabled', PANEL)],
              foreground=[('disabled', MUTED)])
    style.configure('Neptune.TCombobox', fieldbackground=PANEL_ALT, background=PANEL_ALT,
                    foreground=TEXT, arrowcolor=ACCENT, padding=5)
    style.map('Neptune.TCombobox', fieldbackground=[('readonly', PANEL_ALT)],
              foreground=[('readonly', TEXT)])
    style.configure('Neptune.Horizontal.TProgressbar', background=ACCENT, troughcolor=PANEL_ALT,
                    borderwidth=0)


def header(parent, *, logo=None, subtitle='LOCAL TRAINING COMPUTER', version=''):
    """Compact brand row; the same information order is used by the Mac app."""
    row = tk.Frame(parent, bg=INK)
    row.pack(fill='x', pady=(0, 12))
    logo_path = Path(logo) if logo else None
    if logo_path and logo_path.is_file():
        try:
            picture = tk.PhotoImage(file=str(logo_path))
            picture = picture.subsample(max(1, (picture.width() + 51) // 52))
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
    tk.Label(copy, text=version or subtitle, font=('Arial', 9), fg=MUTED, bg=INK,
             anchor='w').pack(fill='x')
    return row


def card(parent, *, padding=12):
    outer = tk.Frame(parent, bg=LINE, padx=1, pady=1)
    outer.pack(fill='x', pady=(0, 10))
    inner = tk.Frame(outer, bg=PANEL, padx=padding, pady=padding)
    inner.pack(fill='both', expand=True)
    return inner


def status(parent, value, *, detail=None, eyebrow='CONNECTION'):
    inner = card(parent)
    tk.Label(inner, text=eyebrow, font=('Arial', 9, 'bold'), fg=ACCENT,
             bg=PANEL, anchor='w').pack(fill='x')
    # Room for four lines whatever the message, so the window never changes size with the text.
    tk.Label(inner, textvariable=value, font=('Arial', 11), fg=TEXT, height=4,
             bg=PANEL, anchor='nw', justify='left', wraplength=500).pack(fill='x', pady=(5, 2))
    if detail is not None:
        tk.Label(inner, text=detail, font=('Arial', 10), fg=MUTED, bg=PANEL,
                 anchor='w', justify='left', wraplength=500).pack(fill='x')
    return inner


def activity(parent):
    ttk.Label(parent, text='ACTIVITY', style='Section.TLabel').pack(anchor='w', pady=(5, 7))
    border = tk.Frame(parent, bg=LINE, padx=1, pady=1)
    border.pack(fill='both', expand=True)
    text = tk.Text(border, height=7, wrap='word', state='disabled', borderwidth=0,
                   highlightthickness=0, bg=LOG, fg=TEXT, insertbackground=TEXT,
                   font=('Menlo', 10), padx=12, pady=10)
    scroll = ttk.Scrollbar(border, orient='vertical', command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side='right', fill='y')
    text.pack(side='left', fill='both', expand=True)
    return text

class ComputerCard(tk.Frame):
    """The desktop equivalent of Neptune's connected-computer card."""
    def __init__(self,parent,*,name,logo=None):
        super().__init__(parent,bg=LINE,padx=1,pady=1)
        self.pack(fill='x',pady=(0,8));self.connected=False;self.working=False
        inner=tk.Frame(self,bg=PANEL,padx=12,pady=10);inner.pack(fill='both',expand=True)
        head=tk.Frame(inner,bg=PANEL);head.pack(fill='x',pady=(0,8))
        if logo and Path(logo).is_file():
            try:
                picture=tk.PhotoImage(file=str(logo));picture=picture.subsample(max(1,(picture.width()+31)//32))
                mark=tk.Label(head,image=picture,bg=PANEL);mark.image=picture;mark.pack(side='left',padx=(0,8))
            except tk.TclError:pass
        copy=tk.Frame(head,bg=PANEL);copy.pack(side='left',fill='x',expand=True)
        tk.Label(copy,text=name,font=('Arial',13,'bold'),fg=TEXT,bg=PANEL,anchor='w').pack(fill='x')
        self.detail=tk.StringVar(value='Reading hardware…');tk.Label(copy,textvariable=self.detail,font=('Arial',9),fg=MUTED,bg=PANEL,anchor='w',wraplength=340,justify='left').pack(fill='x')
        self.badge=tk.StringVar(value='Connecting');tk.Label(head,textvariable=self.badge,font=('Arial',10,'bold'),fg=TEXT,bg=PANEL_ALT,padx=9,pady=5).pack(side='right')
        grid=tk.Frame(inner,bg=PANEL);grid.pack(fill='x');grid.columnconfigure(0,weight=1);grid.columnconfigure(1,weight=1)
        self.meters={}
        for i,label in enumerate(('CPU','GPU','RAM','GPU memory')):
            cell=tk.Frame(grid,bg=PANEL);cell.grid(row=i//2,column=i%2,sticky='ew',padx=(0,12) if i%2==0 else (0,0),pady=(0,8))
            top=tk.Frame(cell,bg=PANEL);top.pack(fill='x')
            tk.Label(top,text=label,font=('Arial',10),fg=MUTED,bg=PANEL).pack(side='left')
            value=tk.StringVar(value='—');tk.Label(top,textvariable=value,font=('Arial',10),fg=TEXT,bg=PANEL).pack(side='right')
            pct=tk.DoubleVar(value=0);ttk.Progressbar(cell,variable=pct,maximum=100,style='Meter.Horizontal.TProgressbar').pack(fill='x',pady=(4,0))
            self.meters[label]=(value,pct)
        self.note=tk.StringVar(value='No assigned job');tk.Label(inner,textvariable=self.note,font=('Arial',9),fg=MUTED,bg=PANEL,anchor='w').pack(fill='x')
    def set_working(self,value):
        self.working=bool(value);self.badge.set('Working' if value else 'Available' if self.connected else 'Connecting');self.note.set('Job in progress' if value else 'No assigned job')
    def set_connected(self,value):
        self.connected=bool(value);self.badge.set('Working' if self.working else 'Available' if value else 'Offline')
    def update_readings(self,payload):
        stats=payload.get('stats') or {};gpu=stats.get('gpu') or {}
        def put(label,pct,value):
            text,bar=self.meters[label];text.set(value);bar.set(max(0,min(100,pct)) if pct is not None else 0)
        for label,data,key in [('CPU',stats,'cpu'),('GPU',gpu,'util')]:
            value=data.get(key);put(label,value,f'{value:g}%' if isinstance(value,(int,float)) else '—')
        for label,data,used,total in [('RAM',stats,'ram_used_mb','ram_total_mb'),('GPU memory',gpu,'mem_used_mb','mem_total_mb')]:
            u,t=data.get(used),data.get(total)
            value='—' if u is None else f'{u/1024:.1f} / {t/1024:.1f} GB' if t else f'{u/1024:.1f} GB'
            put(label,100*u/t if u is not None and t else None,value)
        self.detail.set((payload.get('platform') or 'Computer')+' · '+(gpu.get('name') or 'GPU unavailable'))


class BubblePage(tk.Canvas):
    """Scrolling page of cards over slowly drifting bubbles, like Neptune's dashboard.

    Tk widgets are opaque, so each card is its own canvas window and the bubbles
    show in the gaps between them. Cards stretch to the window width."""
    def __init__(self,parent,*,pad=22,gap=12):
        super().__init__(parent,bg=INK,highlightthickness=0,borderwidth=0)
        self.pad,self.gap,self.items,self.bubbles=pad,gap,[],[]
        import random
        self.random=random.Random(6962)
        self.scroll=ttk.Scrollbar(parent,orient='vertical',command=self.yview);self.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side='right',fill='y');self.pack(side='left',fill='both',expand=True)
        self.bind('<Configure>',lambda event:self.relayout())
        self.bind_all('<MouseWheel>',lambda event:self.yview_scroll(int(-event.delta/(1 if abs(event.delta)<120 else 120)),'units'))
        self.bind_all('<Button-4>',lambda event:self.yview_scroll(-3,'units'));self.bind_all('<Button-5>',lambda event:self.yview_scroll(3,'units'))
        self.after(60,self.drift)
    def add(self,widget):
        """Place a child of this canvas as the next card; returns the widget."""
        self.items.append((widget,self.create_window(0,0,window=widget,anchor='nw')))
        widget.bind('<Configure>',lambda event:self.after_idle(self.relayout),add='+')
        self.after_idle(self.relayout);return widget
    def clear(self,keep=()):
        for widget,item in list(self.items):
            if widget not in keep:self.delete(item);widget.destroy();self.items.remove((widget,item))
    def move_to_end(self,widgets):
        for widget in widgets:
            entry=next((x for x in self.items if x[0] is widget),None)
            if entry:self.items.remove(entry);self.items.append(entry)
        self.after_idle(self.relayout)
    def relayout(self):
        width=max(200,self.winfo_width()-2*self.pad);y=self.pad
        for widget,item in self.items:
            if not widget.winfo_exists():continue
            self.coords(item,self.pad,y);self.itemconfigure(item,width=width)
            y+=widget.winfo_reqheight()+self.gap
        self.configure(scrollregion=(0,0,self.winfo_width(),max(y+self.pad,self.winfo_height())))
    def drift(self):
        if not self.winfo_exists():return
        width,height=max(1,self.winfo_width()),max(1,self.winfo_height())
        while len(self.bubbles)<26:
            r=self.random.uniform(1.5,5);x=self.random.uniform(0,width);y=self.random.uniform(0,height)
            self.bubbles.append([self.create_oval(x-r,y-r,x+r,y+r,outline='#3d5f85',width=1),self.random.uniform(.15,.5)])
        top=self.canvasy(0)
        for bubble in self.bubbles:
            item,speed=bubble;self.move(item,0,-speed)
            x0,y0,x1,y1=self.coords(item)
            if y1<top:
                x=self.random.uniform(0,width);self.coords(item,x,top+height,x+(x1-x0),top+height+(y1-y0))
        self.tag_lower('all');self.after(50,self.drift)


def topbar(parent,*,logo=None):
    """NEPTUNE / TRAINING bar with a status line; returns (bar, status_var, button_row)."""
    bar=tk.Frame(parent,bg=INK,padx=18,pady=10);bar.pack(fill='x')
    if logo and Path(logo).is_file():
        try:
            picture=tk.PhotoImage(file=str(logo));picture=picture.subsample(max(1,(picture.width()+35)//36))
            mark=tk.Label(bar,image=picture,bg=INK);mark.image=picture;mark.pack(side='left',padx=(0,10))
        except tk.TclError:pass
    tk.Label(bar,text='NEPTUNE  /  TRAINING',font=('Arial',12,'bold'),fg=ACCENT,bg=INK).pack(side='left')
    buttons=tk.Frame(bar,bg=INK);buttons.pack(side='right')
    value=tk.StringVar(value='Connecting to Neptune…')
    tk.Label(bar,textvariable=value,font=('Arial',10),fg=MUTED,bg=INK,anchor='w').pack(side='left',fill='x',expand=True,padx=(16,12))
    return bar,value,buttons


def wordmark(parent,logo):
    """The wide Neptune logo as its own card-less row."""
    row=tk.Frame(parent,bg=INK)
    if logo and Path(logo).is_file():
        try:
            picture=tk.PhotoImage(file=str(logo));picture=picture.subsample(max(1,(picture.width()+259)//260))
            label=tk.Label(row,image=picture,bg=INK);label.image=picture;label.pack(anchor='w')
        except tk.TclError:pass
    return row


def page_card(page,title):
    """A bordered card placed on a BubblePage; returns (outer, inner)."""
    outer=tk.Frame(page,bg=LINE,padx=1,pady=1)
    inner=tk.Frame(outer,bg=PANEL,padx=14,pady=12);inner.pack(fill='both',expand=True)
    tk.Label(inner,text=title,font=('Arial',12,'bold'),fg=ACCENT,bg=PANEL,anchor='w').pack(fill='x',pady=(0,6))
    page.add(outer);return outer,inner


def _meter(parent,label,fraction,text):
    cell=tk.Frame(parent,bg=PANEL);top=tk.Frame(cell,bg=PANEL);top.pack(fill='x')
    tk.Label(top,text=label,font=('Arial',10),fg=MUTED,bg=PANEL).pack(side='left')
    tk.Label(top,text=text,font=('Arial',10),fg=TEXT,bg=PANEL).pack(side='right')
    ttk.Progressbar(cell,value=100*max(0,min(1,fraction or 0)),maximum=100,style='Meter.Horizontal.TProgressbar').pack(fill='x',pady=(4,0))
    return cell


def render_dashboard(page,data,*,self_id=None):
    """Neptune's Running now, other helpers and queue as cards; returns the cards made."""
    import time as _time
    computers=data.get('computers') or [];queue=data.get('queue') or []
    running=[x for x in queue if x.get('state')=='running'];waiting=[x for x in queue if x.get('state')=='waiting']
    def label(parent,text,size=11,color=TEXT,weight='normal',font='Arial'):
        tk.Label(parent,text=text,font=(font,size,weight),fg=color,bg=PANEL,anchor='w',justify='left').pack(fill='x',pady=(0,3))
    made=[]
    outer,card=page_card(page,'RUNNING NOW  ·  %d active'%len(running));made.append(outer)
    if running:
        job=running[0];label(card,job.get('title') or 'Training',14,TEXT,'bold');label(card,job.get('message') or '',10,MUTED)
        worker=next((c for c in computers if c.get('id') and c.get('id')==job.get('computer_id')),None)
        if worker:
            k=worker.get('counters') or {}
            if k.get('passes'):
                fraction=((k.get('pass',1)-1)+(k.get('batch',0)/k['batches'] if k.get('batches') else 0))/k['passes']
                label(card,'Stage · pass %s/%s · batch %s/%s'%(k.get('pass','?'),k['passes'],k.get('batch','?'),k.get('batches','?')),10,MUTED)
                _meter(card,'Progress',fraction,'%d%%'%int(100*fraction)).pack(fill='x',pady=(2,8))
            lines=(worker.get('log') or [])[-16:]
            if lines:
                text=tk.Text(card,height=min(10,max(3,len(lines))),bg=LOG,fg='#70bdf7',font=('Menlo',10),borderwidth=0,highlightthickness=0,padx=10,pady=8,wrap='none')
                text.insert('end','\n'.join(_time.strftime('%H:%M',_time.localtime(row[0]))+'  '+str(row[1]) for row in lines if len(row)>1));text.config(state='disabled');text.pack(fill='x')
        if len(running)>1:label(card,'+ %d other active job(s)'%(len(running)-1),10,MUTED)
    else:label(card,'No training job is running.',10,MUTED)
    others=[c for c in computers if not self_id or c.get('id')!=self_id]
    outer,card=page_card(page,'OTHER HELPERS  ·  %d online'%sum(1 for c in others if c.get('online')));made.append(outer)
    if not others:label(card,'No other computers connected.',10,MUTED)
    for index,worker in enumerate(others):
        state='Training' if worker.get('job') else 'Available' if worker.get('online') else 'Offline'
        label(card,(worker.get('name') or worker.get('device') or 'Computer')+'   ·   '+state,12,TEXT,'bold')
        label(card,' · '.join(x for x in (worker.get('platform'),worker.get('device'),worker.get('version')) if x),9,MUTED)
        stats=worker.get('stats') or {};gpu=stats.get('gpu') or {}
        def memory(used,total):
            return '—' if used is None else '%.1f / %.1f GB'%(used/1024,total/1024) if total else '%.1f GB'%(used/1024)
        grid=tk.Frame(card,bg=PANEL);grid.pack(fill='x',pady=(4,4));grid.columnconfigure(0,weight=1,uniform='m');grid.columnconfigure(1,weight=1,uniform='m')
        cells=[('CPU',(stats.get('cpu') or 0)/100,'%g%%'%stats['cpu'] if isinstance(stats.get('cpu'),(int,float)) else '—'),
               ('GPU',(gpu.get('util') or 0)/100,'%g%%'%gpu['util'] if isinstance(gpu.get('util'),(int,float)) else '—'),
               ('RAM',stats['ram_used_mb']/stats['ram_total_mb'] if stats.get('ram_used_mb') is not None and stats.get('ram_total_mb') else None,memory(stats.get('ram_used_mb'),stats.get('ram_total_mb'))),
               ('GPU memory',gpu['mem_used_mb']/gpu['mem_total_mb'] if gpu.get('mem_used_mb') is not None and gpu.get('mem_total_mb') else None,memory(gpu.get('mem_used_mb'),gpu.get('mem_total_mb')))]
        for i,(name,fraction,text) in enumerate(cells):
            _meter(grid,name,fraction,text).grid(row=i//2,column=i%2,sticky='ew',padx=(0,16) if i%2==0 else 0,pady=(0,8))
        label(card,(worker.get('job') or {}).get('message') or 'No assigned job',9,MUTED)
        if index<len(others)-1:tk.Frame(card,bg=LINE,height=1).pack(fill='x',pady=8)
    outer,card=page_card(page,'QUEUE  ·  %d waiting'%len(waiting));made.append(outer)
    if not waiting:label(card,'No jobs waiting.',10,MUTED)
    for item in waiting:label(card,(item.get('title') or 'Job')+' · '+(item.get('message') or 'Waiting'),10)
    return made
