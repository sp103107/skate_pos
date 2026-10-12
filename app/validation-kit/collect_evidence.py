"""Archive existing synthetic validation evidence; installs/runs/publishes nothing."""
from pathlib import Path
import argparse,hashlib,json,zipfile
def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.evidence_dir.resolve();out=a.output.resolve()
    if not root.is_dir() or not (root/'RUN_SUMMARY.json').is_file():p.error('Existing run directory with RUN_SUMMARY.json required')
    if out.exists() or out.with_suffix(out.suffix+'.sha256').exists() or out.is_relative_to(root):p.error('Use new output outside evidence directory')
    files={}
    for f in sorted(root.rglob('*')):
        if f.is_symlink():p.error('Do not include symlinks')
        if f.is_file():
            if f.suffix not in ['.json','.txt','.png']:p.error('Unexpected evidence type:'+f.name)
            files[str(f.relative_to(root))]=f.read_bytes()
    files['RETURN_MANIFEST.json']=(json.dumps({k:hashlib.sha256(v).hexdigest() for k,v in sorted(files.items())},indent=2)+'\n').encode()
    out.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,b in files.items():z.writestr(name,b)
    h=hashlib.sha256(out.read_bytes()).hexdigest();out.with_suffix(out.suffix+'.sha256').write_text(h+'  '+out.name+'\n');print(json.dumps({'output':str(out),'sha256':h,'files':len(files),'uploaded':False}))
if __name__=='__main__':main()
