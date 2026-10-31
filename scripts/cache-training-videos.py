#!/usr/bin/env python3
"""Sequentially cache original labeled training match videos on Neptune; no model training is started."""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'engine'))
import neptune_match_videos as cache
import neptune_robot_labels as labels
from neptune_robot_jobs import region_documents, doc_video


def main():
    p=argparse.ArgumentParser(description=__doc__)
    auth=p.add_mutually_exclusive_group(required=True)
    auth.add_argument('--connection',type=Path)
    auth.add_argument('--mac-keychain',action='store_true',help='Use the existing Mac helper connection without exporting its credential')
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--local-directory',type=Path,action='append',default=[],help='Also reuse original sources from this directory')
    a=p.parse_args()
    config=json.loads(subprocess.check_output(['security','find-generic-password','-a','owner','-s','com.neptunefrc.traininghelper.connection','-w'])) if a.mac_keychain else json.loads(a.connection.read_text())
    docs={d['video_id']:d.get('match_key') or d['video_id'] for d in labels.sync(config) if d.get('frames')}
    from neptune_field_detector import yolo_labels, training_geometry
    for d in region_documents(config):
        vid=doc_video(d)
        if vid and yolo_labels(d) and training_geometry(d):
            docs.setdefault(vid,(d.get('source') or {}).get('match_key') or vid)
    local_sources={}
    for folder in a.local_directory:
        for path in folder.rglob('*.mp4'):
            if path.is_symlink():continue
            vid=path.stem
            if vid not in docs and vid=='source':
                matches=[v for v,k in docs.items() if k in str(path)]
                if len(matches)==1:vid=matches[0]
            if vid in docs and (vid not in local_sources or path.stat().st_size>local_sources[vid].stat().st_size):local_sources[vid]=path
    # Cached originals are also needed for held-out evaluation; this never adds examples to training.
    receipt={'completed':{},'failed':{},'state':'running','matches':len(docs)}
    if a.receipt.is_file():
        previous=json.loads(a.receipt.read_text());receipt['completed']=previous.get('completed',{});receipt['failed']=previous.get('failed',{})
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    def save():
        tmp=a.receipt.with_suffix('.pending');tmp.write_text(json.dumps(receipt,indent=2));tmp.replace(a.receipt)
    for i,(vid,match) in enumerate(sorted(docs.items(),key=lambda x:x[1]),1):
        try:
            info=cache._api(config,'video_cache_info',{'video_id':vid})
            if not info.get('available'):
                video=labels.local_video(vid) or local_sources.get(vid)
                if video is None:
                    video=labels.VIDEOS/(vid+'.mp4');video.parent.mkdir(parents=True,exist_ok=True)
                    time.sleep(8)
                    labels.youtube_download(vid,video)
                # Refuse a partial file or a full-event stream before storing it.
                duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(video)]))
                if not 20<duration<=600:raise ValueError('Not an individual match source')
                info=cache.upload(config,vid,video,lambda message:None)
            receipt['completed'][vid]=dict(info['video'],match_key=match)
            receipt['failed'].pop(vid,None)
            print(f'{i}/{len(docs)} {match}: source cached and verified',flush=True)
        except Exception as e:
            # Exception bodies may contain tokens/URLs; keep the receipt and console bounded to safe categories.
            import urllib.error
            reason=type(e).__name__
            if isinstance(e,urllib.error.HTTPError):
                try:reason=json.loads(e.read(4096)).get('error',f'HTTP {e.code}')
                except Exception:reason=f'HTTP {e.code}'
            elif isinstance(e,(ValueError,RuntimeError)):reason=str(e)[:300]
            receipt['failed'][vid]={'match_key':match,'reason':reason}
            print(f'{i}/{len(docs)} {match}: {reason}',flush=True)
            if labels.youtube_blocked(e) or 'bot check' in reason.lower() or '10 GiB' in reason or isinstance(e,urllib.error.HTTPError) and e.code in (401,403):
                receipt['state']='paused';save();break
        save()
    else:receipt['state']='complete_with_missing' if receipt['failed'] else 'complete';save()
    print('Cache queue:',receipt['state'],'verified',len(receipt['completed']),'missing',len(receipt['failed']),flush=True)


if __name__=='__main__':main()
