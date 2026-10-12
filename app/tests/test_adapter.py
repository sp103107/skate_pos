import unittest,sys,json,uuid,tempfile,sqlite3,threading,http.client,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'adapter'))
from bridge import Adapter,Server,envelope,new_workspace,verify_installed_core,COMMANDS

def snapshot(db):
    with sqlite3.connect(Path(db).as_uri()+'?mode=ro',uri=True) as conn:
        tables=[r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t:conn.execute('SELECT * FROM "'+t.replace('"','""')+'" ORDER BY rowid').fetchall() for t in tables}

class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.identity=verify_installed_core();cls.workspace,cls.core=new_workspace(str(Path(tempfile.gettempdir())/('skate-ui01-demo-tests-'+uuid.uuid4().hex)),True)
        cls.adapter=Adapter(cls.core);cls.server=Server(0,cls.adapter,cls.identity,cls.workspace)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.transcript=[]
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.core.shutdown()
        (cls.workspace/'HTTP_TRANSCRIPT.json').write_text(json.dumps(cls.transcript,indent=2)+'\n')
    def call(self,path,value=None,*,headers=None,method=None,raw=None):
        data=raw if raw is not None else json.dumps(value) if value is not None else None
        h={'Content-Type':'application/json','X-UI01-Token':self.server.token}
        if headers:h.update(headers)
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        c.request(method or ('POST' if data is not None else 'GET'),path,body=data,headers=h)
        r=c.getresponse();body=r.read();status=r.status;c.close()
        try:out=json.loads(body)
        except (ValueError,UnicodeDecodeError):out={'bytes':len(body)}
        self.transcript.append({'path':path,'method':method,'request':value,'raw':raw,'status':status,'response':out})
        return status,out
    def query(self,name,params):return self.call('/api/query',{'name':name,'params':params})
    def no_write(self,fn):
        before=snapshot(self.core.config.sqlite_path);result=fn();self.assertEqual(before,snapshot(self.core.config.sqlite_path));return result
    def test_01_identity_and_seed(self):
        self.assertEqual(self.identity['files_verified'],43);self.assertNotIn('runtime/source',self.identity['origin'])
        status,out=self.call('/api/status');self.assertEqual(status,200);self.assertEqual(out['mode'],'ACTUAL_CORE_SYNTHETIC_ONLY')
        self.assertEqual(len(self.adapter.query({'name':'list_inventory','params':{}})),2)
    def test_02_queries_no_logical_write(self):
        for name,params in [('list_inventory',{}),('get_pair',{'pair_id':'SKT-0900'}),('find_asset',{'identifier':'SKT-0900-L'}),('asset_history',{'pair_id':'SKT-0900'}),('runtime_status',{'deep':True})]:
            with self.subTest(name=name):self.assertEqual(self.no_write(lambda:self.query(name,params))[0],200)
    def test_03_scan_receipt(self):
        status,out=self.call('/api/command',envelope('scan_asset',{'identifier':'SKT-0900-L'}));self.assertEqual(status,200);self.assertEqual(out['receipt']['status'],'ACCEPTED');self.assertEqual(out['receipt']['result']['pair']['pair_id'],'SKT-0900')
    def test_04_transfer_refresh_retry_conflict(self):
        p=self.adapter.query({'name':'get_pair','params':{'pair_id':'SKT-0900'}})
        e=envelope('transfer_location',{'pair_id':'SKT-0900','to_location_id':'LOC-STORAGE'},version=p['version'])
        status,r=self.call('/api/command',e);self.assertEqual(status,200);self.assertEqual(r['receipt']['status'],'ACCEPTED')
        p2=self.adapter.query({'name':'get_pair','params':{'pair_id':'SKT-0900'}});self.assertEqual(p2['current_location_id'],'LOC-STORAGE');self.assertEqual(p2['version'],p['version']+1)
        status,dup=self.no_write(lambda:self.call('/api/command',e));self.assertEqual(dup['receipt']['status'],'DUPLICATE');self.assertEqual(dup['receipt']['event_ids'],r['receipt']['event_ids'])
        changed=copy.deepcopy(e);changed['payload']['to_location_id']='LOC-RINK';status,r=self.no_write(lambda:self.call('/api/command',changed));self.assertEqual(status,409);self.assertEqual(r['receipt']['error']['code'],'IDEMPOTENCY_CONFLICT')
    def test_05_verify_inventory(self):
        p=self.adapter.query({'name':'get_pair','params':{'pair_id':'SKT-0901'}})
        status,r=self.call('/api/command',envelope('verify_inventory',{'pair_id':p['pair_id']},version=p['version']));self.assertEqual(status,200);self.assertEqual(r['receipt']['status'],'ACCEPTED');self.assertTrue(r['receipt']['event_ids'])
    def test_06_stale_version_no_write(self):
        status,r=self.no_write(lambda:self.call('/api/command',envelope('transfer_location',{'pair_id':'SKT-0900','to_location_id':'LOC-RINK'},version=1)))
        self.assertEqual(status,409);self.assertEqual(r['receipt']['error']['code'],'VERSION_CONFLICT')
    def test_07_role_no_write(self):
        e=envelope('transfer_location',{'pair_id':'SKT-0900','to_location_id':'LOC-RINK'});e['actor_role']='NOT_A_ROLE'
        status,r=self.no_write(lambda:self.call('/api/command',e));self.assertEqual(status,422);self.assertEqual(r['receipt']['error']['code'],'ROLE_FORBIDDEN')
    def test_08_reference_no_write(self):
        e=envelope('scan_asset',{'identifier':'SKT-0900'});e['device_id']='DEV-MISSING'
        status,r=self.no_write(lambda:self.call('/api/command',e));self.assertEqual(status,422);self.assertEqual(r['receipt']['error']['code'],'VALIDATION_ERROR')
    def test_09_invalid_envelope_no_write(self):
        e=envelope('scan_asset',{'identifier':'SKT-0900'});e['extra']=True
        status,r=self.no_write(lambda:self.call('/api/command',e));self.assertEqual(status,422);self.assertEqual(r['receipt']['error']['code'],'VALIDATION_ERROR')
    def test_10_gated_operations_no_write(self):
        for name in ['checkout_pair','checkin_pair','complete_cleaning','reserve_inventory','record_correction','transfer_ownership','rebuild_projections','restore_recovery','shell']:
            with self.subTest(name=name):
                status,r=self.no_write(lambda:self.call('/api/command',envelope(name,{})));self.assertEqual(status,400);self.assertEqual(r['error']['code'],'COMMAND_GATED')
    def test_11_invalid_queries_no_write(self):
        for req in [{'name':'list_inventory','params':{'db':'/tmp/other.db'}},{'name':'restore_recovery','params':{}},{'name':'get_pair','params':{'pair_id':0}},{'name':'list_inventory','params':{},'extra':True}]:
            with self.subTest(req=req):self.assertEqual(self.no_write(lambda:self.call('/api/query',req))[0],400)
    def test_12_unknown_asset_no_write(self):
        status,r=self.no_write(lambda:self.call('/api/command',envelope('scan_asset',{'identifier':'NO-ASSET'})));self.assertEqual(status,422);self.assertEqual(r['receipt']['error']['code'],'ASSET_NOT_FOUND')
    def test_13_perimeter_no_write(self):
        for h in [{'Origin':'https://attacker.invalid'},{'Host':'attacker.invalid'},{'X-UI01-Token':''}]:
            with self.subTest(headers=h):self.assertEqual(self.no_write(lambda:self.call('/api/query',{'name':'list_inventory','params':{}},headers=h))[0],403)
    def test_14_methods_paths_no_write(self):
        for path,method in [('/api/runtime','POST'),('/../../etc/passwd','GET'),('/api/command','PUT'),('/api/command','OPTIONS')]:
            with self.subTest(path=path,method=method):self.assertIn(self.no_write(lambda:self.call(path,{},method=method))[0],(404,405))
    def test_15_body_no_write(self):
        for raw in ['{broken','{"name":"list_inventory","name":"get_pair","params":{}}','{"name":"get_pair","params":{"pair_id":NaN}}','[]','x'*17000]:
            with self.subTest(raw=raw[:30]):self.assertIn(self.no_write(lambda:self.call('/api/query',raw=raw))[0],(400,413))
    def test_16_workspace_no_overwrite(self):
        self.assertRaises(ValueError,new_workspace,str(self.workspace),True)
        self.assertRaises(ValueError,new_workspace,str(self.workspace/'nested'),True)
        self.assertRaises(ValueError,new_workspace,'relative-path',True)
    def test_17_static_real_source(self):
        for path in ['/','/app.js','/adapter.js','/app.css','/inventory.png']:self.assertEqual(self.call(path)[0],200)
    def test_18_unavailable_runtime(self):
        # Last test: mount closed Core; never report fake success.
        self.core.shutdown();status,r=self.call('/api/query',{'name':'list_inventory','params':{}});self.assertEqual(status,503);self.assertEqual(r['error']['code'],'RUNTIME_UNAVAILABLE')

if __name__=='__main__':unittest.main(verbosity=2)
