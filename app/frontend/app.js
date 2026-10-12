import {LoopbackAdapter} from './adapter.js';
const $=id=>{const element=document.getElementById(id);if(!element)throw new Error('UI_ELEMENT_MISSING:'+id);return element;};
const button=id=>{const element=$(id);if(!(element instanceof HTMLButtonElement))throw new Error('UI_BUTTON_REQUIRED:'+id);return element;};
const input=id=>{const element=$(id);if(!(element instanceof HTMLInputElement))throw new Error('UI_INPUT_REQUIRED:'+id);return element;};
const select=id=>{const element=$(id);if(!(element instanceof HTMLSelectElement))throw new Error('UI_SELECT_REQUIRED:'+id);return element;};
const navigation=()=>document.querySelectorAll('button[data-view]');const adapter=new LoopbackAdapter();
let pairs=[],assets=[],selected=null,ready=false,busy=false,view='inventory',lastEnvelope=null;
function message(text,kind='amber'){$('message').textContent=text;$('message').className=kind;}
function signedIn(){return !!adapter.sessionToken;}
function controls(){
  for(const id of ['scan-submit','move','verify'])button(id).disabled=!ready||busy||(id!=='scan-submit'&&(!selected||!signedIn()));
  button('login-submit').disabled=!ready||busy;
  button('logout').hidden=!signedIn();
}
function selectView(next){
  view=next;
  const normal=['inventory','assets','runtime','audit'];
  for(const name of normal)$(name+'-view').hidden=name!==view;
  $('gated-view').hidden=normal.includes(view);
  $('workspace-title').textContent=next.charAt(0).toUpperCase()+next.slice(1);
  $('gated-title').textContent=$('workspace-title').textContent+' · Gated';
  navigation().forEach(b=>{b.removeAttribute('aria-current');if(b.getAttribute('data-view')===view)b.setAttribute('aria-current','page');});
  if(view==='runtime')loadHealth();
  if(view==='assets')renderAssets();
  if(view==='audit'&&selected)adapter.query('asset_history',{pair_id:selected.pair_id}).then(h=>{$('history').textContent=JSON.stringify(h,null,2);}).catch(fail);
}
function fail(e){
  if(e.receipt)receipt(e.receipt);
  message(e.message||'RUNTIME_UNAVAILABLE','red');
  if(['Failed to fetch','RUNTIME_UNAVAILABLE','TOKEN_REQUIRED'].includes(e.message)){
    ready=false;$('connection').textContent='Unavailable · reconnect required';$('connection').className='pill red';$('projection').textContent='Stale';
  }
  controls();
}
function render(){
  const filter=input('filter').value.trim().toLowerCase();
  const list=pairs.filter(p=>[p.pair_id,p.size_value,p.current_location_id,p.availability_state].join(' ').toLowerCase().includes(filter));
  $('rows').replaceChildren();$('empty').hidden=list.length!==0;$('count').textContent=String(pairs.length);
  for(const p of list){
    const tr=document.createElement('tr');const td=document.createElement('td'),btn=document.createElement('button');
    btn.textContent=p.pair_id;btn.addEventListener('click',()=>loadPair(p.pair_id));td.append(btn);tr.append(td);
    for(const value of [p.size_value,p.availability_state,p.current_location_id]){const cell=document.createElement('td');cell.textContent=value;tr.append(cell);}
    $('rows').append(tr);
  }
}
function renderAssets(){
  const filter=input('asset-filter').value.trim().toLowerCase();
  const list=assets.filter(a=>{
    const ids=(a.identifiers||[]).map(i=>i.identifier).join(' ');
    return [a.asset_id,a.asset_kind,a.brand,a.size_value,a.side,a.availability_state,ids].join(' ').toLowerCase().includes(filter);
  });
  $('asset-rows').replaceChildren();
  $('asset-empty').hidden=list.length!==0;
  $('asset-count').textContent=String(assets.length);
  const kinds=[...new Set(assets.map(a=>a.asset_kind))].sort();
  $('asset-kinds').textContent=kinds.join(', ')||'—';
  for(const a of list){
    const tr=document.createElement('tr');
    const ids=(a.identifiers||[]).filter(i=>i.active).map(i=>i.identifier).join(', ');
    for(const value of [a.asset_id,a.asset_kind,a.brand||'—',a.size_value||'—',a.side||'—',a.availability_state,ids||'—']){
      const cell=document.createElement('td');cell.textContent=String(value);tr.append(cell);
    }
    $('asset-rows').append(tr);
  }
}
function detail(p){
  selected=p;$('detail').replaceChildren();$('detail-empty').hidden=!!p;$('actions').hidden=!p;
  if(p)for(const [label,key] of [['Pair','pair_id'],['Brand','brand'],['Size','size_value'],['State','availability_state'],['Location','current_location_id'],['Custodian','custodian_org_id'],['Version','version']]){
    const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=String(p[key]??'—');$('detail').append(dt,dd);
  }
  controls();
}
async function loadPair(id){try{const p=await adapter.readPair(id);if(!p)throw new Error('ASSET_NOT_FOUND');detail(p);selectView('inventory');}catch(e){fail(e);}}
function receipt(r){$('receipt-state').textContent=r.status+' · '+r.receipt_id;$('receipt-state').className=r.status==='ACCEPTED'||r.status==='DUPLICATE'?'green':'red';$('receipt').textContent=JSON.stringify(r,null,2);}
function updateStaff(){
  if(adapter.staff)$('staff-state').textContent=`Signed in as ${adapter.staff.display_name} (${adapter.staff.role})`;
  else $('staff-state').textContent='Not signed in';
  controls();
}
function updateModeBanner(status){
  const mode=(status&&status.workspace_mode)||'demo';
  const banner=$('mode-banner');
  banner.textContent=mode.toUpperCase();
  banner.className=mode==='real'?'pill red':'pill amber';
  $('workspace-banner').textContent=mode==='real'
    ? 'REAL workspace · live_activation=false · staff session required for mutations · synthetic seed refused'
    : 'DEMO workspace · synthetic Core successor 0.4.0-a01.1 · staff session required for mutations · not released';
}
async function refresh(){
  if(!ready)return;
  try{
    $('projection').textContent='Loading';
    pairs=await adapter.readInventory();
    assets=await adapter.readAssets();
    render();renderAssets();
    if(selected)detail(await adapter.readPair(selected.pair_id));
    $('projection').textContent='Current';
    $('loaded-at').textContent='Read '+new Date().toLocaleTimeString();
  }catch(e){$('projection').textContent='Stale';fail(e);}
}
async function connect(){
  busy=true;controls();
  try{
    const s=await adapter.connect();
    ready=true;
    updateModeBanner(s);
    $('connection').textContent=s.workspace_mode==='real'?'Actual Core · real':'Actual Core · demo';
    $('connection').className='pill green';
    $('identity').textContent=s.identity.distribution+' · successor '+ (s.identity.successor||'') +' · '+s.origin;
    await refresh();await loadHealth();
    message('Ready. Sign in to mutate. Scan SKT-0900-L or open Assets.','green');
  }catch(e){ready=false;fail(e);}
  finally{busy=false;controls();}
}
async function loadHealth(){
  if(!ready)return;
  try{
    const h=await adapter.health();
    $('health').textContent=JSON.stringify(h,null,2);
    $('health-state').textContent=h.status;
    $('health-state').className=h.status==='HEALTHY'?'green':'red';
    if(h.status!=='HEALTHY')message('Runtime health is '+h.status,'red');
  }catch(e){fail(e);}
}
async function submit(e,scan=false){
  busy=true;lastEnvelope=e;controls();message('Submitting to installed Core…');
  try{
    const r=await adapter.submitCommand(e);receipt(r);
    if(scan){
      if(r.result?.pair)detail(r.result.pair);
      selectView('inventory');
    }
    await refresh();message(r.status+' · receipt '+r.receipt_id,'green');
  }catch(err){
    fail(err);
    if(err.message==='SESSION_REQUIRED')message('Sign in before mutating inventory.','red');
    if(err.receipt?.error?.code==='VERSION_CONFLICT'){$('projection').textContent='Stale';message('VERSION_CONFLICT · projection stale. Refresh before retrying.','red');}
  }finally{busy=false;controls();}
}
navigation().forEach(b=>b.addEventListener('click',()=>selectView(b.getAttribute('data-view'))));
$('scan-form').addEventListener('submit',e=>{e.preventDefault();if(ready&&!busy)submit(adapter.command('scan_asset',{identifier:input('scan-id').value.trim()}),true);});
$('login-form').addEventListener('submit',async e=>{
  e.preventDefault();if(!ready||busy)return;
  busy=true;controls();
  try{
    await adapter.login(input('staff-id').value.trim(),input('staff-pin').value);
    input('staff-pin').value='';
    updateStaff();message('Staff session active.','green');
  }catch(err){fail(err);message('Sign-in failed.','red');}
  finally{busy=false;controls();}
});
button('logout').addEventListener('click',async ()=>{await adapter.logout();updateStaff();message('Signed out.','amber');});
$('filter').addEventListener('input',render);
$('asset-filter').addEventListener('input',renderAssets);
$('refresh').addEventListener('click',connect);
$('move').addEventListener('click',()=>{if(selected&&!busy&&signedIn())submit(adapter.command('transfer_location',{pair_id:selected.pair_id,to_location_id:select('destination').value},selected.version));});
$('verify').addEventListener('click',()=>{if(selected&&!busy&&signedIn())submit(adapter.command('verify_inventory',{pair_id:selected.pair_id},selected.version));});
updateStaff();
connect();
