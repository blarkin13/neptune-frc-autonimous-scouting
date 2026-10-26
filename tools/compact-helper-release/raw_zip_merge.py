"""Replace ZIP entries without recompressing unchanged runtime files.

The small patch ZIP can be transferred to the existing release server, which
reconstructs exactly the same signed archive from its existing base ZIP.
"""
import argparse,copy,zipfile

def merge(base,patch,out):
    with zipfile.ZipFile(base) as a, zipfile.ZipFile(patch) as b, zipfile.ZipFile(out,'w',allowZip64=True) as z:
        names=a.namelist()
        if len(names)!=len(set(names)) or len(b.namelist())!=len(set(b.namelist())):raise ValueError('Duplicate archive names')
        if set(b.namelist())-set(names):raise ValueError('Patch may only replace existing entries')
        ends={}
        for src in (a,b):
            entries=sorted(src.infolist(),key=lambda i:i.header_offset)
            for i,info in enumerate(entries):ends[id(src),info.filename]=entries[i+1].header_offset if i+1<len(entries) else src.start_dir
        for original in a.infolist():
            src=b if original.filename in b.NameToInfo else a
            info=copy.copy(src.getinfo(original.filename));src.fp.seek(info.header_offset)
            raw=src.fp.read(ends[id(src),info.filename]-info.header_offset)
            info.header_offset=z.fp.tell();z.fp.write(raw)
            z.filelist.append(info);z.NameToInfo[info.filename]=info;z._didModify=True;z.start_dir=z.fp.tell()
    with zipfile.ZipFile(out) as z:
        if z.testzip() is not None:raise ValueError('Archive checksum failure')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('base');p.add_argument('patch');p.add_argument('out');a=p.parse_args();merge(a.base,a.patch,a.out)
