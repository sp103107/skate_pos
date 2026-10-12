"""Write fresh Foreman/checker measurements outside the sealed UI candidate."""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,io,json,platform,sqlite3,subprocess,sys,unittest
from importlib import metadata
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--new-evidence-dir',required=True);a=p.parse_args();out=Path(a.new_evidence_dir).resolve()
    if out.exists() or out.is_relative_to(ROOT):p.error('Use a new external evidence directory')
    out.mkdir(parents=True)
    spec=importlib.util.spec_from_file_location('ui01_tests',ROOT/'tests/test_adapter.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    suite=unittest.defaultTestLoader.loadTestsFromModule(m)
    ids=[]
    def collect(s):
        for t in s:
            if isinstance(t,unittest.TestSuite):collect(t)
            else:ids.append(t.id())
    collect(suite);stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'ADAPTER_TEST_LOG.txt').write_text(stream.getvalue())
    result={'status':'PASS_FOREMAN_MEASUREMENT_NOT_JUDGE' if r.wasSuccessful() else 'FAIL','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tests_run':r.testsRun,'passed':r.testsRun-len(r.failures)-len(r.errors)-len(r.skipped),'failures':[(str(t),e) for t,e in r.failures],'errors':[(str(t),e) for t,e in r.errors],'skips':[(str(t),e) for t,e in r.skipped],'case_ids':ids,'subtests_not_additive':True,'environment':{'python':sys.version,'sqlite':sqlite3.sqlite_version,'platform':platform.platform(),'dependencies':{n:metadata.version(n) for n in ['jsonschema','attrs','referencing','rpds-py','jsonschema-specifications','typing-extensions','skate-inventory-core']},'PYTHONPATH':__import__('os').environ.get('PYTHONPATH')},'source_hashes':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [ROOT/'adapter/bridge.py',ROOT/'tests/test_adapter.py']},'synthetic_workspace':str(m.Integration.workspace),'core_identity':m.Integration.identity,'independent_verdict':False}
    (out/'ADAPTER_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'HTTP_TRANSCRIPT.json').write_bytes((m.Integration.workspace/'HTTP_TRANSCRIPT.json').read_bytes())
    (out/'SEED_RECEIPTS.json').write_bytes((m.Integration.workspace/'SEED_RECEIPTS.json').read_bytes())
    print(json.dumps(result));return 0 if r.wasSuccessful() else 1
if __name__=='__main__':sys.exit(main())
