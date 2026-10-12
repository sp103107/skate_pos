"""Deterministically package source/checkpoint, not release or validation authority."""
from pathlib import Path
import argparse,hashlib,io,zipfile
ROOT=Path(__file__).resolve().parents[1]
def _include(f):
    if not f.is_file(): return False
    if '__pycache__' in f.parts or '.local-runtime' in f.parts or '.venv' in f.parts: return False
    if f.name.endswith('.pyc') or f.name=='MANIFEST.sha256': return False
    return True
def build():
    files={str(f.relative_to(ROOT)):f.read_bytes() for f in sorted(ROOT.rglob('*')) if _include(f)}
    manifest=''.join(hashlib.sha256(b).hexdigest()+'  '+p+'\n' for p,b in sorted(files.items())).encode()
    stored=ROOT/'MANIFEST.sha256'
    if stored.exists() and stored.read_bytes()!=manifest:raise ValueError('Manifest mismatch: edited successor needs new identity/binding')
    files['MANIFEST.sha256']=manifest
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p,b in sorted(files.items()):
            i=zipfile.ZipInfo(ROOT.name+'/'+p,date_time=(2026,1,1,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;i.external_attr=0o100644<<16;z.writestr(i,b)
    return out.getvalue(),manifest
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out-dir',required=True);a=parser.parse_args();out=Path(a.out_dir).resolve()
    if out.is_relative_to(ROOT):parser.error('output must be external')
    out.mkdir(parents=True,exist_ok=True);path=out/(ROOT.name+'.zip')
    if path.exists():parser.error('preserve existing package; choose another output directory')
    b,m=build();assert build()[0]==b
    path.write_bytes(b);(out/(path.name+'.sha256')).write_text(hashlib.sha256(b).hexdigest()+'  '+path.name+'\n')
    print(str(path));print(hashlib.sha256(b).hexdigest())
if __name__=='__main__':main()
