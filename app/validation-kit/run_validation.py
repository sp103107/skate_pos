"""Bounded operator-run checker; installs nothing, launches only synthetic loopback UI."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,platform,signal,subprocess,sys,zipfile
sys.dont_write_bytecode=True

ROOT=Path(__file__).resolve().parents[1]
SOURCES=['frontend/app.js','frontend/adapter.js','contracts/runtime-adapter.d.ts','adapter/bridge.py','tests/test_adapter.py','tests/browser_smoke.cjs']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def preflight(core_zip,tools,browser_cache=None):
    if sys.platform!='linux':raise ValueError('Supported route: Linux. Native Windows/macOS NOT_VERIFIED; WSL2 is a Linux route but WSL2 execution NOT_RUN.')
    if tools.is_relative_to(ROOT):raise ValueError('Keep dependency workspace outside sealed candidate')
    if sys.version_info<(3,11) or sys.prefix==sys.base_prefix:raise ValueError('Use separately provisioned Python3.11+ venv; measured version3.12.14.')
    lock=json.loads((ROOT/'lineage/CORE_DEPENDENCY.json').read_text())
    if sha(core_zip)!=lock['core_zip_sha256']:raise ValueError('Frozen Core ZIP hash mismatch')
    with zipfile.ZipFile(core_zip) as z:
        if z.testzip() is not None:raise ValueError('Frozen Core CRC mismatch')
        b=z.read('Skate_Inventory_Use_System_Core_Capsule_v0.3.1-rc.1/releases/wheels/'+lock['wheel_filename'])
        if hashlib.sha256(b).hexdigest()!=lock['wheel_sha256']:raise ValueError('Frozen Core wheel hash mismatch')
    versions={name:json.loads((tools/name/'package.json').read_text())['version'] for name in ['playwright','playwright-core','typescript']}
    if versions!={'playwright':'1.62.1','playwright-core':'1.62.1','typescript':'5.9.3'}:raise ValueError('Locked test tooling mismatch')
    node=subprocess.run(['node','--version'],capture_output=True,text=True,check=True).stdout.strip()
    if int(node[1:].split('.')[0])<20:raise ValueError('Node20+ required; measured Node24.19.0')
    sys.path.insert(0,str(ROOT/'adapter'))
    from bridge import verify_installed_core
    identity=verify_installed_core()
    manifest=ROOT/'MANIFEST.sha256';sealed=False
    if manifest.exists():
        for line in manifest.read_text().splitlines():
            expected,rel=line.split('  ',1);path=(ROOT/rel).resolve()
            if not path.is_relative_to(ROOT) or sha(path)!=expected:raise ValueError('Candidate manifest mismatch:'+rel)
        sealed=True
    descriptor=json.loads((tools/'playwright-core/browsers.json').read_text());expected=next(x for x in descriptor['browsers'] if x['name']=='chromium')
    if expected['revision']!='1234' or expected['browserVersion']!='151.0.7922.34':raise ValueError('Matching Chromium descriptor mismatch')
    executable=None
    if browser_cache is not None:
        env=os.environ.copy();env.update(PLAYWRIGHT_BROWSERS_PATH=str(browser_cache),NODE_PATH=str(tools))
        q=subprocess.run(['node','-e',"process.stdout.write(require('playwright').chromium.executablePath())"],env=env,capture_output=True,text=True,check=True)
        executable=Path(q.stdout.strip())
        if not executable.is_file():raise ValueError('Matching Chromium executable absent; preflight never installs/downloads')
    return {'status':'PREFLIGHT_PASS_NOT_BROWSER_OR_JUDGE_PASS','python':sys.version,'platform':platform.platform(),'node':node,'tool_versions':versions,'core_identity':identity,'core_zip_sha256':sha(core_zip),'core_wheel_sha256':lock['wheel_sha256'],'candidate_manifest_verified':sealed,'source_hashes':{f:sha(ROOT/f) for f in SOURCES},'expected_browser':expected,'browser_executable':str(executable) if executable else None,'browser_executable_sha256':sha(executable) if executable else None,'browser_launch':'NOT_RUN','external_authority':'NOT_GRANTED_BY_SCRIPT'}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['preflight','checks','browser'],default='preflight');p.add_argument('--core-zip',type=Path,required=True);p.add_argument('--node-tools',type=Path,required=True,help='External node_modules containing locked tools');p.add_argument('--browser-cache',type=Path);p.add_argument('--new-evidence-dir',type=Path);p.add_argument('--operator-execution-authorized',action='store_true',help='Attestation of separately granted local browser execution; this flag cannot grant authority');a=p.parse_args()
    try:
        core=a.core_zip.resolve();tools=a.node_tools.resolve()
        if a.mode=='browser' and (not a.operator_execution_authorized or a.browser_cache is None):raise ValueError('Browser mode requires prior explicit environment/execution authorization and an already provisioned task-local browser cache')
        info=preflight(core,tools,a.browser_cache.resolve() if a.mode=='browser' else None)
        if a.mode=='preflight':print(json.dumps(info,indent=2));return 0
        if a.new_evidence_dir is None:raise ValueError('Use NEW external evidence directory')
        out=a.new_evidence_dir.resolve()
        if out.exists() or out.is_relative_to(ROOT):raise ValueError('Evidence directory must be new and external')
        out.mkdir(parents=True);(out/'PREFLIGHT.json').write_text(json.dumps(info,indent=2)+'\n')
        env=os.environ.copy();env.pop('PYTHONPATH',None);env.update(NODE_PATH=str(tools),PYTHONDONTWRITEBYTECODE='1')
        results=[]
        def run(label,cmd,timeout):
            try:
                process=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
                try:
                    stdout,stderr=process.communicate(timeout=timeout)
                    record={'label':label,'command':cmd,'exit_code':process.returncode,'stdout':stdout,'stderr':stderr,'timeout':False}
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);stdout,stderr=process.communicate()
                    record={'label':label,'command':cmd,'exit_code':None,'timeout':True,'process_group_stopped':True,'stdout':stdout,'stderr':stderr}
            except OSError as e:
                record={'label':label,'command':cmd,'exit_code':None,'timeout':False,'error':str(e)}
            results.append(record);(out/(label+'.json')).write_text(json.dumps(record,indent=2)+'\n');return record['exit_code']==0
        ok=True
        if a.mode=='checks':
            ok=run('TYPECHECK',['node',str(tools/'typescript/bin/tsc'),'--allowJs','--checkJs','--noEmit','--target','es2022','--module','es2022',*[str(ROOT/f) for f in SOURCES[:3]]],60) and ok
            for f in ['frontend/app.js','frontend/adapter.js','tests/browser_smoke.cjs']:ok=run('SYNTAX_'+Path(f).stem.replace('.','_'),['node','--check',str(ROOT/f)],30) and ok
            ok=run('ADAPTER',[sys.executable,str(ROOT/'scripts/validate.py'),'--new-evidence-dir',str(out/'adapter')],120) and ok
        else:
            env.update(PLAYWRIGHT_BROWSERS_PATH=str(a.browser_cache.resolve()),UI01_PYTHON=sys.executable,UI01_EVIDENCE_DIR=str(out/'browser'))
            ok=run('BROWSER',['node',str(ROOT/'tests/browser_smoke.cjs')],90)
        browser_result=out/'browser/BROWSER_RESULT.json';actual=json.loads(browser_result.read_text()) if browser_result.exists() else {}
        summary={'status':'PASS_SCOPED_OPERATOR_MEASUREMENT_NOT_JUDGE' if ok else 'FAIL','mode':a.mode,'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'result_files':[r['label']+'.json' for r in results],'browser_invoked':a.mode=='browser','browser_launched':actual.get('browser_launched',False),'browser_cases':len(actual.get('checks',[])),'independent_review':False,'UI01_completion':False,'core_unchanged':True,'screenshots_require_operator_visual_review':True}
        (out/'RUN_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary));return 0 if ok else 1
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as e:print(str(e),file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
