#!/usr/bin/env python3
"""Smoke checks against the actual embedded runtime, without using host Python libraries."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('app',type=Path);a=p.parse_args();r=a.app/'Contents/Resources'
code='''import sys,json,subprocess
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import torch,torchvision,numpy,cv2,yt_dlp,ultralytics,neptune_ocr,neptune_engine
root=Path(sys.argv[1]); tools=root/'vendor/bin'
subprocess.run([str(tools/'qjs'),'--eval','if (1 + 1 !== 2) throw new Error("runtime check failed")'],check=True)
filters=subprocess.check_output([str(tools/'ffmpeg'),'-hide_banner','-filters'],text=True)
for name in ('fps','crop','split','scale','format'):assert any(line.split()[1:2]==[name] for line in filters.splitlines())
backend=neptune_ocr.select_backend();print(json.dumps({'engine':neptune_engine.identity()['version'],'torch':torch.__version__,'mps':torch.backends.mps.is_available(),'ocr':backend.describe(),'numpy':numpy.__version__}))
if torch.backends.mps.is_available():assert (torch.ones(2,device='mps')+1).cpu().tolist()==[2.,2.]
'''
subprocess.run([str(r/'python/bin/python3.13'),'-I','-B','-c',code,str(r/'engine')],check=True)
