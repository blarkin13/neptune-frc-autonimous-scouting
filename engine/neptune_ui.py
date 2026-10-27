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
SIDEBAR = '#0d1c33'
WARN = '#fac76b'
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
        inner=self.inner=tk.Frame(self,bg=PANEL,padx=12,pady=10);inner.pack(fill='both',expand=True)
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
    """Scrolling page of cards; cards stretch to the window width."""
    def __init__(self,parent,*,pad=22,gap=12):
        super().__init__(parent,bg=INK,highlightthickness=0,borderwidth=0)
        self.pad,self.gap,self.items=pad,gap,[]
        self.scroll=ttk.Scrollbar(parent,orient='vertical',command=self.yview);self.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side='right',fill='y');self.pack(side='left',fill='both',expand=True)
        self.bind('<Configure>',lambda event:self.relayout())
        self.bind_all('<MouseWheel>',lambda event:self.yview_scroll(int(-event.delta/(1 if abs(event.delta)<120 else 120)),'units'))
        self.bind_all('<Button-4>',lambda event:self.yview_scroll(-3,'units'));self.bind_all('<Button-5>',lambda event:self.yview_scroll(3,'units'))
    def add(self,widget):
        """Place a child of this canvas as the next card; returns the widget."""
        self.items.append((widget,self.create_window(0,0,window=widget,anchor='nw')))
        if not getattr(widget,'_relayout_bound',False):
            widget.bind('<Configure>',lambda event:self.after_idle(self.relayout),add='+');widget._relayout_bound=True
        self.after_idle(self.relayout);return widget
    def show_only(self,keep):
        """Start a new page: lift every card off the canvas, destroying all but `keep`, which are re-added later."""
        for widget,item in self.items:
            self.delete(item)
            if widget not in keep:widget.destroy()
        self.items=[];self.yview_moveto(0)
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
def page_card(page,title):
    """A bordered card placed on a BubblePage; returns (outer, inner)."""
    outer=tk.Frame(page,bg=LINE,padx=1,pady=1)
    inner=tk.Frame(outer,bg=PANEL,padx=14,pady=12);inner.pack(fill='both',expand=True)
    if title:tk.Label(inner,text=title,font=('Arial',12,'bold'),fg=TEXT,bg=PANEL,anchor='w').pack(fill='x',pady=(0,6))
    page.add(outer);return outer,inner


def _meter(parent,label,fraction,text):
    cell=tk.Frame(parent,bg=PANEL);top=tk.Frame(cell,bg=PANEL);top.pack(fill='x')
    tk.Label(top,text=label,font=('Arial',10),fg=MUTED,bg=PANEL).pack(side='left')
    tk.Label(top,text=text,font=('Arial',10),fg=TEXT,bg=PANEL).pack(side='right')
    ttk.Progressbar(cell,value=100*max(0,min(1,fraction or 0)),maximum=100,style='Meter.Horizontal.TProgressbar').pack(fill='x',pady=(4,0))
    return cell


class Shell:
    """Sidebar of pages beside a header and a scrolling page of cards, the same layout as the Mac app."""
    PAGES=[('overview','Overview'),('robots','Robots'),('field','Field'),('actions','Actions'),('computers','Computers'),('activity','Activity')]
    def __init__(self,root,*,logo=None,on_page=lambda key:None):
        self.on_page=on_page;self.nav={}
        side=tk.Frame(root,bg=SIDEBAR,width=210,padx=12,pady=16);side.pack(side='left',fill='y');side.pack_propagate(False)
        tk.Frame(root,bg=LINE,width=1).pack(side='left',fill='y')
        # The wide NEPTUNE wordmark across the sidebar.
        brand=tk.Frame(side,bg=SIDEBAR);brand.pack(fill='x',pady=(0,18))
        if logo and Path(logo).is_file():
            try:
                picture=tk.PhotoImage(file=str(logo));picture=picture.subsample(max(1,(picture.width()+185)//186))
                mark=tk.Label(brand,image=picture,bg=SIDEBAR);mark.image=picture;mark.pack(anchor='w')
            except tk.TclError:tk.Label(brand,text='NEPTUNE',font=('Arial',18,'bold'),fg=TEXT,bg=SIDEBAR,anchor='w').pack(fill='x')
        tk.Label(brand,text='TRAINING HELPER',font=('Arial',8,'bold'),fg=MUTED,bg=SIDEBAR,anchor='w').pack(fill='x',pady=(4,0))
        def section(title):tk.Label(side,text=title.upper(),font=('Arial',8,'bold'),fg=MUTED,bg=SIDEBAR,anchor='w').pack(fill='x',pady=(14,4))
        for i,(key,title) in enumerate(self.PAGES):
            if i==1:section('Models')
            if i==4:section('Helpers')
            item=tk.Label(side,text=title,font=('Arial',11),fg=TEXT,bg=SIDEBAR,anchor='w',padx=10,pady=6,cursor='hand2')
            item.pack(fill='x');item.bind('<Button-1>',lambda event,k=key:self.on_page(k));self.nav[key]=item
        section('Tools')
        self.tools=tk.Frame(side,bg=SIDEBAR);self.tools.pack(fill='x')
        footer=tk.Frame(side,bg=LINE,padx=1,pady=1);footer.pack(side='bottom',fill='x')
        self.footer=tk.Frame(footer,bg=PANEL,padx=10,pady=10);self.footer.pack(fill='both')
        main=tk.Frame(root,bg=INK);main.pack(side='left',fill='both',expand=True)
        head=tk.Frame(main,bg=INK,padx=22,pady=14);head.pack(fill='x')
        self.title=tk.StringVar(value='Overview');self.status=tk.StringVar(value='Connecting to Neptune…')
        words=tk.Frame(head,bg=INK);words.pack(side='left',fill='x',expand=True)
        tk.Label(words,textvariable=self.title,font=('Arial',19,'bold'),fg=TEXT,bg=INK,anchor='w').pack(fill='x')
        tk.Label(words,textvariable=self.status,font=('Arial',10),fg=MUTED,bg=INK,anchor='w').pack(fill='x')
        self.right=tk.Frame(head,bg=INK);self.right.pack(side='right')
        self.actions=tk.Frame(head,bg=INK);self.actions.pack(side='right',padx=(0,8))
        holder=tk.Frame(main,bg=INK);holder.pack(fill='both',expand=True)
        self.page=BubblePage(holder)
    def select(self,key):
        for k,item in self.nav.items():item.configure(bg=PANEL_ALT if k==key else SIDEBAR,fg=ACCENT if k==key else TEXT)
        self.title.set(dict(self.PAGES).get(key,'Overview'))
        for child in self.actions.winfo_children():child.destroy()


def tool_button(shell,text,command):
    """A sidebar tool: looks like a page link, runs a command."""
    item=tk.Label(shell.tools,text=text,font=('Arial',11),fg=TEXT,bg=SIDEBAR,anchor='w',padx=10,pady=6,cursor='hand2')
    item.pack(fill='x');item.bind('<Button-1>',lambda event:command());return item


def _when(t):
    import time as _time
    return _time.strftime('%b %d, %H:%M',_time.localtime(t)) if isinstance(t,(int,float)) and t>0 else '—'


def score(kind,p):
    """Robot detector: held-out F1. Field detector: targets and corners placed, and how far off."""
    if not isinstance(p,dict):return '—'
    if kind=='robot':return 'F1 %.2f'%p['f1'] if isinstance(p.get('f1'),(int,float)) else '—'
    if not p.get('found') or not isinstance(p.get('mean_error'),(int,float)):return 'none found'
    return '%d/%d · %.1f%% off'%(p['found'],p.get('expected',0),p['mean_error']*100)


def run_result(r):
    state=r.get('state')
    if state=='done':return ('Switched to it',GOOD) if r.get('adopted') else ('Kept the one in use',MUTED)
    return {'failed':('Failed',WARN),'cancelled':('Cancelled',MUTED),'claimed':('Running',ACCENT)}.get(state,('Waiting',MUTED))


def _label(parent,text,size=11,color=TEXT,weight='normal',font='Arial',bg=PANEL):
    tk.Label(parent,text=text,font=(font,size,weight),fg=color,bg=bg,anchor='w',justify='left').pack(fill='x',pady=(0,3))


def tiles(page,specs):
    """A row of equal tiles: (label, value, note, note colour, click handler or None)."""
    row=tk.Frame(page,bg=INK)
    for i,(label,value,note,color,click) in enumerate(specs):
        row.columnconfigure(i,weight=1,uniform='tile')
        outer=tk.Frame(row,bg=LINE,padx=1,pady=1);outer.grid(row=0,column=i,sticky='nsew',padx=(0 if i==0 else 6,0 if i==len(specs)-1 else 6))
        inner=tk.Frame(outer,bg=PANEL,padx=14,pady=12,cursor='hand2' if click else '');inner.pack(fill='both',expand=True)
        for text,size,col,weight in ((label,10,MUTED,'normal'),(value,17,TEXT,'bold'),(note,9,color or MUTED,'normal')):
            w=tk.Label(inner,text=text,font=('Arial',size,weight),fg=col,bg=PANEL,anchor='w');w.pack(fill='x')
            if click:w.bind('<Button-1>',lambda event,c=click:c())
        if click:inner.bind('<Button-1>',lambda event,c=click:c())
    page.add(row);return row


def model_tiles(page,models,open_page):
    robot,field,actions=models.get('robot'),models.get('field'),models.get('actions')
    tagged=((actions or {}).get('counts') or {}).get('matches') or 0
    tiles(page,[
        ('Robots',score('robot',(robot.get('current') or {}).get('new')) if robot and robot.get('current') else ('Built-in' if robot else '—'),'%d labelled matches'%(robot.get('matches') or 0) if robot else 'Loading…',None,lambda:open_page('robots')),
        ('Field',score('field',(field.get('current') or {}).get('new')) if field and field.get('current') else ('Marked zones' if field else '—'),'%d events marked'%len(field.get('events') or []) if field else 'Loading…',None,lambda:open_page('field')),
        ('Actions',('Released' if actions.get('released') else 'Not released') if actions else '—',('%d tagged matches'%tagged+(' · needs more' if tagged<6 else '')) if actions else 'Loading…',WARN if actions and tagged<6 else None,lambda:open_page('actions')),
    ])


def _clock(seconds):
    s=max(0,round(seconds));return '%d:%02d:%02d'%(s//3600,s//60%60,s%60) if s>=3600 else '%d:%02d'%(s//60,s%60)


def console(page,job,worker,*,self_id=None):
    """One running job as the website's console: part and helper, step and match, live readings,
    stage and overall bars, next steps and recent log."""
    import re,time
    lines=(job.get('message') or '').splitlines()
    get=lambda prefix:next((l[len(prefix):].strip() for l in lines if l.startswith(prefix)),'')
    now=re.sub(r'^Training (robot|field) detector: ','',get('Now:'))
    step=next((re.sub(r'^.*? · step (\d+ of \d+): ?',r'Step \1 · ',l) for l in lines if ' · step ' in l),None)
    log=[(row[0],str(row[1])) for row in (worker or {}).get('log') or [] if len(row)>1]
    elapsed=time.time()-job['started'] if isinstance(job.get('started'),(int,float)) and job['started']>0 else None
    overall=None;eta=''
    m=re.match(r'(\d+)%(?: · (.*))?',get('Progress:'))
    if m:overall=float(m.group(1));eta=re.sub(r'^about ','~',m.group(2) or '')
    else:
        p=re.search(r'pass (\d+) of up to (\d+)(?: · batch (\d+) of (\d+))?',now)
        if p and int(p.group(2)):
            # Detector runs report passes, not an overall figure; same estimate as the website.
            f=((int(p.group(1))-1)+(int(p.group(3))/max(1,int(p.group(4))) if p.group(3) else 0))/int(p.group(2));overall=round(100*(.1+.82*f))
            if elapsed and elapsed>60 and overall>3:
                left=elapsed/(overall/100)*(1-overall/100);eta='~%d min left'%(left/60) if left<3600 else '~%.1f h left'%(left/3600)
    k=(worker or {}).get('counters') or {};stage=None;stage_text=''
    if k.get('passes'):
        stage=100*((k.get('pass',1)-1)+(k.get('batch',0)/k['batches'] if k.get('batches') else 0))/k['passes']
        stage_text='pass %s/%s · batch %s/%s'%(k.get('pass','?'),k['passes'],k.get('batch','?'),k.get('batches','?'))+(' · %s it/s'%k['it_s'] if k.get('it_s') else '')
    elif k.get('matches'):stage=100*max(0,(k.get('match') or 0)-1)/k['matches'];stage_text='match %s of %s'%(k.get('match',0),k['matches'])
    else:
        found=next((re.search(r'\[(\d+)/(\d+)\]',t) for t in [now]+[l for _,l in reversed(log)] if re.search(r'\[(\d+)/(\d+)\]',t)),None)
        if found and int(found.group(2)):stage=100*(int(found.group(1))-1)/int(found.group(2));stage_text='match %s of %s'%(found.group(1),found.group(2))
    key=r'\b(\d{4}[a-z0-9]+_[a-z0-9]+)\b';match=re.search(key,now) or (re.search(key,log[-1][1]) if log else None)
    stats=(worker or {}).get('stats') or {};gpu=stats.get('gpu') or {}
    gb=lambda mb:('%.1f' if mb<10240 else '%.0f')%(mb/1024)
    sys_line=' · '.join(x for x in ['GPU %d%%'%gpu['util'] if isinstance(gpu.get('util'),(int,float)) else '',
        'VRAM '+gb(gpu['mem_used_mb'])+('/'+gb(gpu['mem_total_mb']) if gpu.get('mem_total_mb') else '')+' GB' if isinstance(gpu.get('mem_used_mb'),(int,float)) else '',
        '%d°C'%gpu['temp_c'] if isinstance(gpu.get('temp_c'),(int,float)) else '','CPU %d%%'%stats['cpu'] if isinstance(stats.get('cpu'),(int,float)) else '',
        'RAM %s/%s GB'%(gb(stats.get('ram_used_mb') or 0),gb(stats['ram_total_mb'])) if stats.get('ram_total_mb') else ''] if x)
    mono='Menlo'
    _,card=page_card(page,None)
    head=tk.Frame(card,bg=PANEL);head.pack(fill='x',pady=(0,4))
    tk.Label(head,text='● '+(job.get('label') or job.get('title') or 'Training'),font=(mono,11,'bold'),fg=ACCENT,bg=PANEL).pack(side='left')
    helper='waiting for its helper' if not worker else (worker.get('name') or 'Computer')+(' (this computer)' if worker.get('id')==self_id else '')+(' · '+gpu['name'].replace('NVIDIA GeForce ','') if gpu.get('name') else '')
    tk.Label(head,text=helper,font=(mono,10),fg=MUTED,bg=PANEL).pack(side='right')
    _label(card,(step or job.get('title') or '')+(' · '+match.group(1) if match else ''),12,TEXT,'bold',mono)
    _label(card,sys_line or 'no live readings from this helper yet',10,ACCENT,font=mono)
    def bar_row(label,p,detail):
        row=tk.Frame(card,bg=PANEL);row.pack(fill='x',pady=2)
        tk.Label(row,text=label,font=(mono,11),fg=TEXT,bg=PANEL,width=8,anchor='w').pack(side='left')
        track=tk.Frame(row,bg='#0f1d31',width=240,height=8);track.pack(side='left',padx=(0,10));track.pack_propagate(False)
        if p:tk.Frame(track,bg='#8fb6de',width=max(1,int(240*min(100,p)/100)),height=8).place(x=0,y=0)
        tk.Label(row,text='  —' if p is None else '%3d%%'%round(p),font=(mono,11,'bold'),fg=TEXT,bg=PANEL).pack(side='left')
        tk.Label(row,text=detail,font=(mono,11),fg=MUTED,bg=PANEL,anchor='w').pack(side='left',padx=(10,0))
    bar_row('stage',stage,stage_text or now or '—')
    bar_row('overall',overall,' · '.join(x for x in [_clock(elapsed)+' elapsed' if elapsed else '',eta or ('estimating' if overall is not None else '')] if x))
    if get('Next:'):_label(card,'next → '+get('Next:'),10,MUTED,font=mono)
    for t,message in log[-6:]:
        low=message.lower()
        color='#fa8c8c' if re.search('fail|error|could not|refused|timed out',low) else WARN if re.search('warn|skipp|retry|missing',low) else GOOD if re.search('finish|saved|adopted|done|complete|kept|passed',low) else '#8cc7f7'
        _label(card,time.strftime('%H:%M:%S',time.localtime(t))+'  '+message,10,color,font=mono)


def render_overview(page,dash,models,*,self_id=None,busy=False,open_page=lambda k:None):
    """Running now (other computers when this one is busy), the three models, and the queue."""
    computers=dash.get('computers') or [];queue=dash.get('queue') or []
    running=[q for q in queue if q.get('state')=='running']
    if not running:_,card=page_card(page,'Running now');_label(card,'Nothing is running. Start a run from a model page.',10,MUTED)
    for job in running[:3]:
        # Detector runs name their helper in computer_id; action runs in target.
        helper=job.get('computer_id') or job.get('target')
        console(page,job,next((c for c in computers if helper and c.get('id')==helper),None),self_id=self_id)
    model_tiles(page,models,open_page)
    waiting=[q for q in queue if q.get('state')=='waiting']
    _,card=page_card(page,'Queue · %d waiting'%len(waiting))
    if not waiting:_label(card,'No runs waiting.',10,MUTED)
    for item in waiting:_label(card,(item.get('title') or 'Run')+' · '+(item.get('message') or 'Waiting'),10)


def render_model(page,kind,m,*,open_url=lambda url:None,connected=True):
    """A detector's page: the model in use, its held-out match, its data and the last runs."""
    if not m:
        _,card=page_card(page,None);_label(card,'Loading this model’s status…' if connected else 'Connect this computer to Neptune to see this model.',10,MUTED);return
    current=m.get('current')
    data=('%d matches'%(m.get('matches') or 0),'%d labelled frames'%(m.get('frames') or 0)) if kind=='robot' else ('%d matches'%(m.get('marked') or 0),', '.join(m.get('events') or []) or '—')
    tiles(page,[('Model in use',score(kind,current.get('new')) if current else 'Built-in','Adopted '+_when(current.get('adopted_at')) if current else 'No retrained model has passed the check yet',None,None),
                ('Checked on',m.get('holdout') or '—','Held out · never trained on',None,None),
                ('Labelled data' if kind=='robot' else 'Marked data',data[0],data[1],None,None)])
    if kind=='field':_,card=page_card(page,None);_label(card,'Scouting uses your marked zones. Mark one match at each event you scout; training this detector is optional.',10,MUTED)
    elif not m.get('ready'):_,card=page_card(page,None);_label(card,'Label robots in at least two matches on Neptune before training.',10,WARN)
    _,card=page_card(page,'Recent runs')
    runs=m.get('runs') or []
    if not runs:_label(card,'No runs yet.',10,MUTED)
    for i,r in enumerate(runs):
        row=tk.Frame(card,bg=PANEL);row.pack(fill='x')
        result,color=run_result(r)
        tk.Label(row,text=_when(r.get('created_at')),font=('Arial',10),fg=MUTED,bg=PANEL,width=14,anchor='w').pack(side='left')
        tk.Label(row,text=result,font=('Arial',10,'bold'),fg=color,bg=PANEL,width=17,anchor='w').pack(side='left')
        versus='—' if not isinstance(r.get('new'),dict) else score(kind,r['new'])+' vs '+(score(kind,r['current']) if isinstance(r.get('current'),dict) else 'none')
        tk.Label(row,text=versus,font=('Arial',10),fg=TEXT,bg=PANEL,anchor='w').pack(side='left')
        review=r.get('review') or {}
        if isinstance(review.get('youtube_id'),str) and len(review['youtube_id'])==11:
            watch=tk.Label(row,text='▶ Watch',font=('Arial',10),fg=ACCENT,bg=PANEL,cursor='hand2');watch.pack(side='right')
            watch.bind('<Button-1>',lambda event,u='https://youtu.be/'+review['youtube_id']:open_url(u))
        elif review.get('status')=='upload_failed':tk.Label(row,text='Video upload failed',font=('Arial',9),fg=MUTED,bg=PANEL).pack(side='right')
        if r.get('message'):_label(card,r['message'],9,MUTED)
        if i<len(runs)-1:tk.Frame(card,bg=LINE,height=1).pack(fill='x',pady=6)


def render_actions(page,a,*,connected=True):
    if not a:
        _,card=page_card(page,None);_label(card,'Loading the action model’s status…' if connected else 'Connect this computer to Neptune to see the action model.',10,MUTED);return
    counts=a.get('counts') or {};tagged=counts.get('matches') or 0;latest=a.get('latest')
    tiles(page,[('Model in use','Released' if a.get('released') else 'None released','Latest trained '+_when(latest.get('created_at')) if latest else 'No model trained yet',None,None),
                ('Tagged matches',str(tagged),'Needs tagged matches from more events' if tagged<6 else 'Human-tagged',WARN if tagged<6 else None,None),
                ('Human tags',str(counts.get('tags') or 0),'%d imported actions'%(counts.get('external') or 0),None,None)])
    _,card=page_card(page,'Improve this model')
    _label(card,'Tag scoring, climbing and defense in matches from events not tagged yet; more variety helps more than more of one event.',10,MUTED)
    _label(card,'Train on Neptune picks the matches and the computer, then Test & release checks the new model before it’s used.',10,MUTED)


def render_computers(page,dash,*,self_id=None):
    """Every connected computer with its live readings; this one first."""
    computers=sorted(dash.get('computers') or [],key=lambda c:c.get('id')!=self_id)
    if not computers:_,card=page_card(page,None);_label(card,'No computer readouts yet.',10,MUTED)
    for w in computers:
        _,card=page_card(page,None)
        state,color=('Training',ACCENT) if w.get('job') else (('Available',GOOD) if w.get('online') else ('Offline',MUTED))
        head=tk.Frame(card,bg=PANEL);head.pack(fill='x')
        tk.Label(head,text=(w.get('name') or 'Computer')+(' · this computer' if w.get('id')==self_id else ''),font=('Arial',12,'bold'),fg=TEXT,bg=PANEL).pack(side='left')
        tk.Label(head,text=state,font=('Arial',10,'bold'),fg=color,bg=PANEL).pack(side='left',padx=10)
        _label(card,' · '.join(x for x in (w.get('platform'),w.get('device'),w.get('version')) if x),9,MUTED)
        stats=w.get('stats') or {};gpu=stats.get('gpu') or {}
        def memory(used,total):return '—' if used is None else '%.1f / %.1f GB'%(used/1024,total/1024) if total else '%.1f GB'%(used/1024)
        grid=tk.Frame(card,bg=PANEL);grid.pack(fill='x',pady=(4,4))
        cells=[('CPU',(stats.get('cpu') or 0)/100,'%g%%'%stats['cpu'] if isinstance(stats.get('cpu'),(int,float)) else '—'),
               ('GPU',(gpu.get('util') or 0)/100,'%g%%'%gpu['util'] if isinstance(gpu.get('util'),(int,float)) else '—'),
               ('RAM',stats['ram_used_mb']/stats['ram_total_mb'] if stats.get('ram_used_mb') is not None and stats.get('ram_total_mb') else None,memory(stats.get('ram_used_mb'),stats.get('ram_total_mb'))),
               ('GPU memory',gpu['mem_used_mb']/gpu['mem_total_mb'] if gpu.get('mem_used_mb') is not None and gpu.get('mem_total_mb') else None,memory(gpu.get('mem_used_mb'),gpu.get('mem_total_mb')))]
        for i,(name,fraction,text) in enumerate(cells):
            grid.columnconfigure(i,weight=1,uniform='m');_meter(grid,name,fraction,text).grid(row=0,column=i,sticky='ew',padx=(0,14) if i<3 else 0)
        _label(card,(w.get('job') or {}).get('message') or 'No assigned job',9,MUTED)
