"""Shared model status. Training and model releases belong to Neptune's server."""
import queue
import threading
import tkinter as tk
from tkinter import ttk
import webbrowser
import neptune_games as games
from neptune_shared_models import refresh


class TrainingPanel:
    def __init__(self,parent):
        self.parent=parent;self.messages=queue.Queue();self.running=False
        self.page=ttk.Frame(parent.tabs,padding=20);parent.tabs.add(self.page,text='4. Shared models')
        ttk.Label(self.page,text='One shared model for each game',font=('',18,'bold')).pack(anchor='w')
        ttk.Label(self.page,text='Community tags are stored on Neptune. Training, evaluation and model releases run on the server. This helper checks for the released model when you start a match. You do not need to train anything.',wraplength=800).pack(anchor='w',pady=14)
        line=ttk.Frame(self.page);line.pack(fill='x',pady=8)
        ttk.Label(line,text='Season').pack(side='left')
        self.year=tk.StringVar(value=parent.season.get())
        ttk.Combobox(line,textvariable=self.year,values=sorted(games.profiles()),state='readonly',width=9).pack(side='left',padx=10)
        self.button=ttk.Button(line,text='Check shared model',command=self.check);self.button.pack(side='left')
        self.info=tk.StringVar(value='No shared tag model has been checked yet. Match browsing does not require one.')
        ttk.Label(self.page,textvariable=self.info,wraplength=800).pack(anchor='w',pady=14)
        ttk.Button(self.page,text='View community training data',command=lambda:webbrowser.open(parent.site.get().rstrip('/')+'/community/training-labels.php')).pack(anchor='w')
        parent.root.after(200,self.poll)

    def check(self):
        if self.running:return
        site=self.parent.site.get();year=self.year.get();self.running=True;self.button.configure(state='disabled')
        self.info.set('Checking Neptune’s shared model…')
        def work():
            try:
                data,game,model=refresh(site,year,self.parent.state)
                self.messages.put('Shared '+game['game']+' model: '+model['model_id'][:16] if model else 'No evaluated '+game['game']+' tag model is released yet. Scoreboard and bumper reading are still available where the game’s video reader is supported. Training is managed on Neptune.')
            except Exception as e:self.messages.put(str(e) if isinstance(e,ValueError) else 'Could not reach Neptune. Retry when connected to the internet.')
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            text=self.messages.get_nowait();self.running=False;self.button.configure(state='normal');self.info.set(text)
        except queue.Empty:pass
        self.parent.root.after(200,self.poll)
