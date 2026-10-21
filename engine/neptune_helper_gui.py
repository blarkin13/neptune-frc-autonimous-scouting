#!/usr/bin/env python3
"""Installed Neptune Helper: one-click setup, progress, preview and explicit submit."""
import json
import datetime
import urllib.parse
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from neptune_helper import public_https, request
from neptune_setup import LocalSetup, MODEL, logs_folder, open_folder
from neptune_connect import connect_account


class HelperWindow:
    def __init__(self, root):
        self.root = root
        self.messages = queue.Queue()
        self.process = None
        self.busy = False
        self.prepared = False
        self.runtime = LocalSetup()
        self.ready = False
        self.result_path = None
        self.operation = None
        self.review_heartbeat = None
        self.state = Path.home() / '.neptune-helper'
        version_file=Path(__file__).with_name('build-version.json')
        version=json.loads(version_file.read_text()).get('version','development') if version_file.is_file() else 'development'
        root.title('Neptune Helper · '+version)
        root.geometry('950x780')
        root.minsize(780, 650)
        frame = ttk.Frame(root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Neptune Helper', font=('', 26, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='Version '+version+' · Shared models managed by Neptune').pack(anchor='w')
        ttk.Label(frame, text='Choose a match. Let this computer work. Review the results before submitting.').pack(anchor='w', pady=(3, 16))
        self.tabs = ttk.Notebook(frame)
        self.tabs.pack(fill='both', expand=True)
        self.setup_tab, self.work_tab, self.results_tab = [ttk.Frame(self.tabs, padding=20) for _ in range(3)]
        for page, name in [(self.setup_tab, '1. Set up'), (self.work_tab, '2. Choose a match'), (self.results_tab, '3. Results')]:
            self.tabs.add(page, text=name)
        ttk.Label(self.setup_tab, text='Setup handles the required software for you.', font=('', 17, 'bold')).pack(anchor='w')
        ttk.Label(self.setup_tab, text='The installer provides Python, video tools and the text reader. Setup checks them before each session.\nMatches are read from the scoreboard and bumper numbers with on-device text recognition; no AI model download is needed.\nNo paid AI service or manual commands are required.', wraplength=800).pack(anchor='w', pady=12)
        self.setup_button = ttk.Button(self.setup_tab, text='Check this computer', command=self.setup)
        self.setup_button.pack(anchor='w', pady=8)
        ttk.Label(self.setup_tab, text='Connect your Neptune account', font=('', 17, 'bold')).pack(anchor='w', pady=(25, 8))
        self.site = tk.StringVar(value='https://neptunefrc.com')
        self.token = tk.StringVar()
        self.connecting = False
        self.connect_stop = threading.Event()
        self.connect_button = ttk.Button(self.setup_tab, text='Connect to Neptune', command=self.connect)
        self.connect_button.pack(anchor='w')
        self.cancel_connect_button=ttk.Button(self.setup_tab,text='Cancel connection',command=lambda:self.connect_stop.set(),state='disabled')
        self.cancel_connect_button.pack(anchor='w',pady=5)
        self.connection_label = tk.StringVar(value='Connect using your Neptune browser login. No token to copy.')
        ttk.Label(self.setup_tab, textvariable=self.connection_label, wraplength=800).pack(anchor='w', pady=8)
        ttk.Label(self.setup_tab, text='Pilot: text recognition can misread numbers. Facts marked uncertain or unknown are not confirmed. Review against the video before submitting.', wraplength=800).pack(anchor='w', pady=20)
        ttk.Button(self.setup_tab, text='Open helper logs', command=self.open_logs).pack(anchor='w')
        filters=ttk.Frame(self.work_tab)
        filters.pack(fill='x',pady=(0,12))
        ttk.Label(filters,text='Season').pack(side='left')
        self.season=tk.StringVar(value=str(max(2026,datetime.date.today().year)))
        self.season_picker=ttk.Combobox(filters,textvariable=self.season,values=[str(y) for y in range(2025,max(2026,datetime.date.today().year)+2)],state='readonly',width=7)
        self.season_picker.pack(side='left',padx=8)
        self.season_picker.bind('<<ComboboxSelected>>',lambda event:self.load_events())
        ttk.Label(filters,text='Event').pack(side='left')
        self.event_picker=ttk.Combobox(filters,state='readonly',width=62)
        self.event_picker.pack(side='left',padx=8,fill='x',expand=True)
        self.event_picker.bind('<<ComboboxSelected>>',lambda event:self.load())
        self.events=[]
        controls = ttk.Frame(self.work_tab)
        controls.pack(fill='x', pady=(0, 12))
        self.refresh_events = ttk.Button(controls, text='Reload events', command=self.load_events)
        self.refresh_events.pack(side='left', padx=(0,8))
        self.refresh = ttk.Button(controls, text='Refresh matches', command=self.load)
        self.refresh.pack(side='left')
        self.start = ttk.Button(controls, text='Go', command=self.run, state='disabled')
        self.start.pack(side='left', padx=12)
        self.stop = ttk.Button(controls, text='Stop and release match', command=self.cancel, state='disabled')
        self.stop.pack(side='left')
        self.saved_draft = ttk.Frame(self.work_tab)
        self.saved_draft_text = tk.StringVar()
        ttk.Label(self.saved_draft, textvariable=self.saved_draft_text, wraplength=760).pack(anchor='w')
        ttk.Button(self.saved_draft, text='Review saved draft', command=lambda:self.tabs.select(self.results_tab)).pack(side='left',pady=6)
        self.release_saved = ttk.Button(self.saved_draft, text='Release saved match', command=self.release)
        self.release_saved.pack(side='left',padx=10,pady=6)
        self.matches = ttk.Treeview(self.work_tab, columns=('match', 'status', 'coverage'), show='headings', height=12)
        self.matches.heading('match', text='Match')
        self.matches.heading('status', text='Status')
        self.matches.column('match', width=550)
        self.matches.column('status', width=130)
        self.matches.heading('coverage', text='Prior human tagging')
        self.matches.column('coverage', width=230)
        self.matches.pack(fill='both', expand=True)
        ttk.Label(self.results_tab, text='Review your draft', font=('', 17, 'bold')).pack(anchor='w')
        self.result_view = tk.Text(self.results_tab, wrap='word', height=18, padx=12, pady=12, state='disabled')
        self.result_view.pack(fill='both', expand=True, pady=12)
        buttons = ttk.Frame(self.results_tab)
        buttons.pack(fill='x')
        self.submit_button = ttk.Button(buttons, text='Submit results', command=self.submit, state='disabled')
        self.submit_button.pack(side='left')
        self.source_button = ttk.Button(buttons, text='Open source video', command=self.open_source, state='disabled')
        self.source_button.pack(side='left', padx=12)
        self.discard_button = ttk.Button(buttons, text='Release match', command=self.release, state='disabled')
        self.discard_button.pack(side='left')
        self.status = tk.StringVar(value='Click Check this computer to get started.')
        ttk.Label(frame, textvariable=self.status, wraplength=880).pack(anchor='w', pady=(16, 7))
        self.bar = ttk.Progressbar(frame, mode='indeterminate')
        self.bar.pack(fill='x')
        from neptune_training_gui import TrainingPanel
        self.training_panel=TrainingPanel(self)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(150, self.pump)
        root.after(400, self.setup)

    def open_logs(self):
        open_folder(logs_folder())

    def activity(self, text):
        self.busy = True
        self.status.set(text)
        self.bar.start(12)
        self.start.configure(state='disabled')
        self.setup_button.configure(state='disabled')
        self.connect_button.configure(state='disabled')
        self.refresh.configure(state='disabled')
        self.refresh_events.configure(state='disabled')
        self.submit_button.configure(state='disabled')
        self.discard_button.configure(state='disabled')
        self.release_saved.configure(state='disabled')
        self.season_picker.configure(state='disabled')
        self.event_picker.configure(state='disabled')

    def idle(self):
        self.busy = False
        self.bar.stop()
        self.season_picker.configure(state='readonly')
        self.event_picker.configure(state='readonly')
        self.setup_button.configure(state='normal')
        self.connect_button.configure(state='normal')
        self.refresh.configure(state='normal')
        self.refresh_events.configure(state='normal')
        self.start.configure(state='normal' if self.ready and not self.prepared else 'disabled')
        self.stop.configure(state='disabled')
        self.submit_button.configure(state='normal' if self.prepared else 'disabled')
        self.discard_button.configure(state='normal' if self.prepared else 'disabled')
        self.release_saved.configure(state='normal' if self.prepared else 'disabled')

    def setup(self):
        if self.busy or self.prepared:
            return
        self.activity('Checking this computer…')
        def work():
            try:
                self.runtime.install(lambda text: self.messages.put(('progress', text)))
                self.messages.put(('setup_done', None))
            except Exception as exc:
                self.messages.put(('error', str(exc) if isinstance(exc, ValueError) else 'Setup could not finish. Check your internet connection and retry.'))
        threading.Thread(target=work, daemon=True).start()

    def connect(self):
        if self.busy:
            return
        self.connecting = True
        self.connect_stop.clear()
        self.cancel_connect_button.configure(state='normal')
        self.activity('Opening Neptune in your browser…')
        self.stop.configure(text='Cancel connection',state='normal')
        site=self.site.get()
        def work():
            try:
                result=connect_account(site,lambda text:self.messages.put(('connect_progress',text)),self.connect_stop)
                self.messages.put(('connected',result))
            except Exception as exc:
                self.messages.put(('connect_error',str(exc) if isinstance(exc,ValueError) else 'Could not reach Neptune. Check your internet connection, then try again.'))
        threading.Thread(target=work,daemon=True).start()

    def load_events(self):
        if self.busy:
            return
        year=self.season.get()
        self.event_picker.set('')
        self.events=[]
        self.activity('Loading events for '+year+'…')
        site=self.site.get()
        def work():
            try:
                result=request(public_https(site+'/api/community-analysis.php?action=events&season='+year))
                self.messages.put(('events',result['events']))
            except Exception as exc:
                self.messages.put(('error',str(exc) if isinstance(exc,ValueError) else 'Could not load events. Check your connection and retry.'))
        threading.Thread(target=work,daemon=True).start()

    def load(self):
        if self.busy:
            return
        index=self.event_picker.current()
        if index<0 or index>=len(self.events):
            self.load_events()
            return
        event_key=self.events[index]['key']
        site = self.site.get()
        self.activity('Loading matches and video links…')
        def work():
            try:
                result = request(public_https(site + '/api/community-analysis.php?action=event_matches&event='+urllib.parse.quote(event_key,safe='')))
                self.messages.put(('matches', result['matches']))
            except ValueError as exc:
                self.messages.put(('error',str(exc)))
            except Exception:
                self.messages.put(('error','Could not reach Neptune. Check your internet connection and try again.'))
        threading.Thread(target=work, daemon=True).start()

    def selected_match(self):
        selected = self.matches.selection()
        return selected[0] if selected else None

    def start_worker(self, mode, match):
        args = ['--site', self.site.get(), '--match', str(match), '--state', str(self.state), '--pipeline', self.runtime.pipeline]
        if self.runtime.pipeline == 'ai':
            args += ['--model', MODEL, '--endpoint', self.runtime.base + '/v1/chat/completions']
        if mode == 'prepare':
            args.append('--prepare-only')
        elif mode == 'submit':
            args.append('--submit')
        elif mode == 'release':
            args.append('--release')
        if getattr(sys, 'frozen', False):
            command = [sys.executable, '--worker'] + args
        else:
            command = [sys.executable, str(Path(__file__).with_name('neptune_app.py')), '--worker'] + args
        environment = dict(os.environ, NEPTUNE_HELPER_TOKEN=self.token.get().strip(), PYTHONUNBUFFERED='1')
        self.operation = mode
        self.last_worker_error=''
        self.activity({'prepare':'Starting match…', 'submit':'Submitting your reviewed results…', 'release':'Releasing match…'}[mode])
        try:
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            self.process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, creationflags=flags)
        except OSError:
            self.idle()
            self.status.set('Could not start processing. Reinstall Neptune Helper.')
            return
        self.stop.configure(state='normal' if mode == 'prepare' else 'disabled')
        process = self.process
        def watch():
            log_path=logs_folder()/'processing.log'
            log_path.touch(mode=0o600,exist_ok=True)
            os.chmod(log_path,0o600)
            for line in process.stdout:
                text=line.strip().replace(environment['NEPTUNE_HELPER_TOKEN'],'[redacted]') if environment['NEPTUNE_HELPER_TOKEN'] else line.strip()
                with log_path.open('a') as log:log.write(text+'\n')
                if text.startswith('ERROR '):
                    self.messages.put(('worker_error',text[6:]))
                    continue
                if text.startswith('RESULT_READY '):
                    self.messages.put(('result_path', text[len('RESULT_READY '):]))
                else:
                    self.messages.put(('progress', text))
            self.messages.put(('done', (mode, process.wait())))
        threading.Thread(target=watch, daemon=True).start()

    def run(self):
        if self.busy:
            return
        if self.prepared:
            self.tabs.select(self.results_tab)
            self.status.set('Your saved draft is ready. Submit it or release its match before starting another. You can still browse events.')
            return
        match = self.selected_match()
        if not self.ready:
            self.tabs.select(self.setup_tab)
            messagebox.showinfo('Check this computer', 'Click Check this computer first.')
            return
        if not match or self.matches.set(match, 'status') != 'available':
            messagebox.showinfo('Choose a match', 'Select an available match before clicking Go.')
            return
        if not self.token.get().strip():
            self.connect()
            return
        self.start_worker('prepare', match)

    def show_results(self):
        payload = json.loads(self.result_path.read_text())
        lines = [payload['summary'], '\nTimestamped observations (elapsed video time):']
        for row in payload['observations']:
            seconds = row['start_ms'] // 1000
            team = 'Team ' + str(row['team']) if row['team'] is not None else 'Unidentified robot / field'
            lines.append(f"\n{seconds//60}:{seconds%60:02} · {team} · {row['certainty']}\n{row['note']}")
        self.result_view.configure(state='normal')
        self.result_view.delete('1.0', 'end')
        self.result_view.insert('1.0', '\n'.join(lines))
        self.result_view.configure(state='disabled')
        self.prepared = True
        claim=json.loads((self.state/'active.json').read_text())
        self.saved_draft_text.set('Saved draft: '+claim['match'].get('title',claim['match'].get('key','match'))+'. Browse freely; submit or release this match before starting another.')
        self.saved_draft.pack(before=self.matches,fill='x',pady=(0,10))
        self.release_saved.configure(state='normal')
        self.submit_button.configure(state='normal')
        self.source_button.configure(state='normal')
        self.discard_button.configure(state='normal')
        self.tabs.select(self.results_tab)
        self.renew_review()

    def renew_review(self):
        if not self.prepared:
            return
        if self.review_heartbeat:
            self.root.after_cancel(self.review_heartbeat)
            self.review_heartbeat=None
        token = self.token.get().strip()
        site = self.site.get()
        if not token:
            return
        def renew():
            try:
                claim = json.loads((self.state/'active.json').read_text())
                auth = {k: claim[k] for k in ('attempt_id', 'lease_token')}
                request(public_https(site+'/api/community-analysis.php?action=heartbeat'), dict(auth, stage='Contributor reviewing draft'), token)
            except Exception:
                self.messages.put(('lease_error', None))
        threading.Thread(target=renew, daemon=True).start()
        self.review_heartbeat = self.root.after(30000, self.renew_review)

    def submit(self):
        if not self.prepared or self.busy:
            return
        if not self.token.get().strip():
            self.connect()
            return
        claim = json.loads((self.state/'active.json').read_text())
        self.start_worker('submit', claim['match']['id'])

    def release(self):
        if self.busy or not (self.state/'active.json').is_file():
            return
        if not self.token.get().strip():
            self.connect()
            return
        claim = json.loads((self.state/'active.json').read_text())
        self.start_worker('release', claim['match']['id'])

    def open_source(self):
        claim = json.loads((self.state/'active.json').read_text())
        webbrowser.open(public_https(claim['match']['source_url']))

    def cancel(self):
        if self.connecting:
            self.connect_stop.set()
            return
        if self.process:
            # The worker releases the match on interrupt (Ctrl+Break on Windows, which it maps to an interrupt).
            self.process.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGINT)
            self.status.set('Stopping and releasing this match…')
        elif (self.state/'active.json').is_file():
            self.release()

    def finish_draft(self):
        self.prepared = False
        self.saved_draft.pack_forget()
        if self.review_heartbeat:
            self.root.after_cancel(self.review_heartbeat)
            self.review_heartbeat = None
        self.submit_button.configure(state='disabled')
        self.source_button.configure(state='disabled')
        self.discard_button.configure(state='disabled')

    def pump(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()
                if kind == 'setup_done':
                    self.ready = True
                    self.idle()
                    self.status.set('This computer is ready. Click Connect to Neptune to sign in through your browser.')
                    # Recover an unsubmitted local draft after restarting the helper.
                    saved = self.state/'active.json'
                    if saved.exists():
                        claim = json.loads(saved.read_text())
                        result = self.state/(claim['attempt_id']+'-result.json')
                        if result.exists():
                            self.result_path = result
                            self.show_results()
                            self.status.set('Recovered your saved draft. Connect your Neptune account to submit or release it.')
                    self.load_events()
                elif kind == 'connect_progress':
                    self.status.set(value)
                    self.connection_label.set(value)
                elif kind == 'connected':
                    self.connecting=False
                    self.cancel_connect_button.configure(state='disabled')
                    self.token.set(value['access_token'])
                    self.connection_label.set('Connected as '+value['display_name']+'. This connection stays active while the helper is open.')
                    self.stop.configure(text='Stop and release match')
                    self.idle()
                    if self.prepared:
                        self.submit_button.configure(state='normal')
                        self.renew_review()
                        self.status.set('Connected. Review your recovered draft, then submit or release it.')
                    else:
                        self.status.set('Connected to Neptune. Finding available matches…')
                        self.load()
                elif kind == 'connect_error':
                    self.connecting=False
                    self.cancel_connect_button.configure(state='disabled')
                    self.stop.configure(text='Stop and release match')
                    self.idle()
                    self.connection_label.set(value)
                    self.status.set(value)
                    messagebox.showerror('Connect to Neptune',value)
                elif kind == 'events':
                    self.idle()
                    self.events=value
                    self.event_picker.configure(values=[(e.get('start_date') or 'Date TBD')+' · '+e['name']+' ('+e['key']+')' for e in value])
                    self.matches.delete(*self.matches.get_children())
                    self.tabs.select(self.work_tab)
                    self.status.set(str(len(value))+' events loaded. Choose an event to load its matches. Sign in when you are ready to start.' if value else 'No events are published for '+self.season.get()+'. Try another season, or Reload events later.')
                    if self.prepared:self.status.set(str(len(value))+' events loaded. Your saved draft is kept; use Review saved draft to return to it.')
                elif kind == 'matches':
                    self.idle()
                    self.matches.delete(*self.matches.get_children())
                    for row in value:
                        self.matches.insert('', 'end', iid=str(row['id']), values=(row['title'], row['work_status'], ('%s entries · %s/6 robots (partial)' % (row['coverage']['labels'],row['coverage']['robots_tagged'])) if row.get('coverage',{}).get('available') else 'Not available'))
                    self.tabs.select(self.work_tab)
                    self.status.set('Select an available match and click Go. Video needed means no match video is published yet.' if value else 'The event has no published match schedule yet. Try Refresh matches later.')
                elif kind == 'error':
                    self.idle()
                    self.status.set(value)
                    messagebox.showerror('Neptune Helper', value)
                elif kind == 'progress':
                    if value:
                        self.status.set(value)
                elif kind == 'result_path':
                    self.result_path = Path(value)
                elif kind == 'lease_error':
                    if self.prepared and not self.busy:
                        self.status.set('Could not renew the match reservation. Reconnect your account; an expired reservation may require processing again.')
                elif kind == 'worker_error':
                    self.last_worker_error=value
                    self.status.set(value)
                elif kind == 'done':
                    mode, code = value
                    self.process = None
                    if code == 0 and mode == 'prepare' and self.result_path:
                        self.idle()
                        self.show_results()
                        self.refresh.configure(state='normal')
                        self.start.configure(state='disabled')
                        self.status.set('Results ready. Review the draft and source video, then click Submit results.')
                    elif code == 0 and mode in ('submit', 'release'):
                        self.finish_draft()
                        self.idle()
                        self.status.set('Results submitted for independent review. Thank you!' if mode == 'submit' else 'Match released. Your local draft is retained.')
                    else:
                        self.idle()
                        if self.prepared:
                            self.submit_button.configure(state='normal')
                        detail=getattr(self,'last_worker_error','') or 'Work stopped before a draft was completed. Retry this match, or release it to choose another. Details are in processing.log.'
                        self.status.set(detail)
                        if (self.state/'active.json').is_file():
                            self.stop.configure(state='normal')
                        messagebox.showerror('Match processing stopped',detail)
        except queue.Empty:
            pass
        except (OSError, ValueError, KeyError):
            self.idle()
            self.status.set('Could not read the saved draft. Contact the Neptune owner for help.')
        self.root.after(150, self.pump)

    def close(self):
        if self.busy or self.process:
            messagebox.showinfo('Work in progress', 'Wait for setup to finish, or stop the current match, before closing.')
            return
        if self.review_heartbeat:
            self.root.after_cancel(self.review_heartbeat)
            self.review_heartbeat=None
        # The draft is already saved on disk. Closing does not submit, release or erase it.
        self.runtime.close()
        self.root.destroy()


if __name__ == '__main__':
    from neptune_app import main
    raise SystemExit(main())
