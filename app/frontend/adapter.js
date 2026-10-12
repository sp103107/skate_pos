// @ts-check
/** @typedef {import('../contracts/runtime-adapter').CommandEnvelope} CommandEnvelope */
/** @typedef {import('../contracts/runtime-adapter').CommandReceipt} CommandReceipt */
/** @typedef {import('../contracts/runtime-adapter').Pair} Pair */
/** @typedef {import('../contracts/runtime-adapter').RuntimeAdapter} RuntimeAdapter */
/** @implements {RuntimeAdapter} */
export class LoopbackAdapter {
  constructor(){
    this.token='';
    this.sessionToken='';
    this.context={actor_id:'',actor_role:'',device_id:'',location_id:''};
    this.staff=null;
    this.status=null;
  }
  async connect(){
    const r=await fetch('/api/status',{cache:'no-store'});
    if(!r.ok)throw new Error('RUNTIME_UNAVAILABLE');
    const s=await r.json();
    this.token=s.token;
    this.context=s.context;
    this.status=s;
    return s;
  }
  headers(){
    const h={'Content-Type':'application/json','X-UI01-Token':this.token};
    if(this.sessionToken)h['X-Staff-Session']=this.sessionToken;
    return h;
  }
  async request(path,value){
    const response=await fetch(path,{method:'POST',headers:this.headers(),body:JSON.stringify(value)});
    const body=await response.json();
    if(!response.ok){
      const error=new Error(body.receipt?.error?.code||body.error?.code||'RUNTIME_UNAVAILABLE');
      Object.assign(error,{receipt:body.receipt,httpStatus:response.status});
      throw error;
    }
    return body;
  }
  async login(staff_id,pin){
    const body=await this.request('/api/session/login',{staff_id,pin});
    this.sessionToken=body.result.session_token;
    this.staff=body.result.staff;
    this.context={...this.context,actor_id:this.staff.staff_id,actor_role:this.staff.role};
    return body.result;
  }
  async logout(){
    try{await this.request('/api/session/logout',{});}catch(_){/* ignore */}
    this.sessionToken='';
    this.staff=null;
    this.context={...this.context,actor_id:'',actor_role:''};
  }
  async query(name,params){return (await this.request('/api/query',{name,params})).result;}
  /** @param {CommandEnvelope} envelope @returns {Promise<CommandReceipt>} */
  async submitCommand(envelope){return (await this.request('/api/command',envelope)).receipt;}
  /** @returns {Promise<Pair[]>} */
  async readInventory(){return this.query('list_inventory',{});}
  async readPair(pair_id){return this.query('get_pair',{pair_id});}
  async readAssets(){return this.query('list_assets',{});}
  async health(){return this.query('runtime_status',{deep:true});}
  /** @returns {CommandEnvelope} */
  command(command_name,payload,version){
    return {
      command_id:crypto.randomUUID(),
      schema_version:'0.1.0',
      command_name,
      requested_at:new Date().toISOString(),
      ...this.context,
      idempotency_key:'ui01:'+crypto.randomUUID(),
      payload,
      offline_created:false,
      ...(version===undefined?{}:{expected_pair_version:version})
    };
  }
}
