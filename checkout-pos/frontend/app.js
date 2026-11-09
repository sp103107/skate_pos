const $ = (id) => document.getElementById(id);
const money = (cents) => `$${(cents / 100).toFixed(2)}`;
const cart = new Map();
let catalog = [], quote = null, activeSale = null, busy = false;

function dollarsToCents(raw) {
  const value = raw.trim();
  if (!/^\d+(?:\.\d{1,2})?$/.test(value)) throw new Error('Discount must be a nonnegative dollar amount with at most two decimals.');
  const [dollars, fraction = ''] = value.split('.');
  const n = Number(dollars) * 100 + Number(fraction.padEnd(2, '0'));
  if (!Number.isSafeInteger(n) || n > 100_000_000) throw new Error('Discount is too large.');
  return n;
}
async function api(path, payload) {
  const response = await fetch(path, payload === undefined ? {cache: 'no-store'} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
  const json = await response.json();
  if (!response.ok) throw new Error(json.error?.message || json.error?.code || 'Unable to reach POS');
  return json;
}
function status(text, error=false) {
  $('status-text').textContent = text;
  $('status-text').className = error ? 'status-line error' : 'status-line';
}
function cartPayload() {
  return {lines:Array.from(cart.entries()).map(([sku, quantity]) => ({sku,quantity})), discount_minor:dollarsToCents($('discount').value)};
}
function setControls() {
  const hasCart = cart.size > 0;
  $('create-sale').disabled = busy || !hasCart || !quote || activeSale !== null;
  $('simulate-payment').disabled = busy || !activeSale || activeSale.status !== 'DRAFT';
  $('clear').disabled = busy;
  $('discount').disabled = busy || !!activeSale;
  $('products').querySelectorAll('button').forEach(b => b.disabled = busy || !!activeSale);
}
function renderCatalog() {
  const root = $('products'); root.replaceChildren();
  for (const item of catalog) {
    const b = document.createElement('button'); b.type='button'; b.className='product';
    const type = document.createElement('span'); type.className='type'; type.textContent=item.kind==='RENTAL_DEMO'?'RENTAL · DEMO ONLY':'RETAIL';
    const name = document.createElement('span'); name.className='name'; name.textContent=item.name;
    const cost = document.createElement('span'); cost.className='cost'; cost.textContent=money(item.price_minor);
    b.append(type,name,cost);
    b.addEventListener('click', () => {cart.set(item.sku, Math.min((cart.get(item.sku)||0)+1, 99)); activeSale=null; renderCart();refreshQuote();});
    root.append(b);
  }
  setControls();
}
function renderCart() {
  const root=$('cart'); root.replaceChildren();
  if (!cart.size) {const p=document.createElement('p');p.className='empty';p.textContent='No items added.';root.append(p);}
  for(const [sku, qty] of cart){
    const item=catalog.find(x=>x.sku===sku); if(!item)continue;
    const row=document.createElement('div');row.className='cart-row';
    const label=document.createElement('div');label.className='cart-label';label.textContent=item.name;
    const sub=document.createElement('small');sub.textContent=`${money(item.price_minor)} each`;label.append(sub);
    const actions=document.createElement('div');actions.className='quantity';
    const minus=document.createElement('button');minus.type='button';minus.textContent='−';minus.setAttribute('aria-label',`Remove one ${item.name}`);
    minus.addEventListener('click',()=>{if(qty<=1)cart.delete(sku);else cart.set(sku,qty-1);renderCart();refreshQuote();});
    const count=document.createElement('span');count.textContent=String(qty);
    const plus=document.createElement('button');plus.type='button';plus.textContent='+';plus.setAttribute('aria-label',`Add one ${item.name}`);plus.disabled=qty>=99;
    plus.addEventListener('click',()=>{cart.set(sku,qty+1);renderCart();refreshQuote();});
    actions.append(minus,count,plus);row.append(label,actions);root.append(row);
  }
  setControls();
}
function renderQuote(data) {
  $('subtotal').textContent=money(data?.subtotal_minor||0);
  $('discount-show').textContent=money(data?.discount_minor||0);
  $('tax').textContent=money(data?.tax_minor||0);
  $('total').textContent=money(data?.total_minor||0);
  $('tax-state').textContent=data?.tax_status==='DEMO_CONFIGURED'?'Demo rate':'Unconfigured';
  setControls();
}
let quoteSeq = 0;
async function refreshQuote() {
  const seq=++quoteSeq; quote=null;renderQuote(null);
  if (!cart.size){status('Add a product to start a demo sale.');return;}
  try {
    const result=await api('/api/quote',cartPayload());
    if(seq!==quoteSeq)return;
    quote=result;renderQuote(result);status(result.tax_status==='UNCONFIGURED'?'Tax not configured. Demo quote only.':'Demo quote ready.');
  }catch(e){if(seq===quoteSeq)status(e.message,true);}
}
function renderReceipt(sale){
  $('receipt').hidden=false;
  $('receipt-id').textContent=sale.sale_id;
  $('receipt-state').textContent=`Status: ${sale.status.replaceAll('_',' ')} · ${new Date(sale.created_at).toLocaleString()}`;
  const root=$('receipt-lines');root.replaceChildren();
  for(const line of sale.lines){const row=document.createElement('div');row.className='receipt-line';
    const name=document.createElement('span');name.textContent=`${line.quantity} × ${line.name}`;
    const cost=document.createElement('span');cost.textContent=money(line.extended_minor-line.discount_minor+line.tax_minor);
    row.append(name,cost);root.append(row);}
  $('receipt-total').textContent=`Total: ${money(sale.total_minor)} · Tax: ${sale.tax_status}`;
}
$('discount').addEventListener('input',()=>{if(!activeSale)refreshQuote();});
$('clear').addEventListener('click',()=>{cart.clear();activeSale=null;quote=null;$('discount').value='0.00';$('receipt').hidden=true;renderCart();refreshQuote();});
$('create-sale').addEventListener('click',async()=>{
  if(busy||!quote||activeSale)return;
  busy=true;setControls();status('Creating demo sale…');
  try{activeSale=await api('/api/sales',{...cartPayload(),request_id:crypto.randomUUID()});renderReceipt(activeSale);status('Draft demo sale recorded. You may simulate payment.');}
  catch(e){status(e.message,true);}finally{busy=false;setControls();}
});
$('simulate-payment').addEventListener('click',async()=>{
  if(busy||!activeSale||activeSale.status!=='DRAFT')return;
  busy=true;setControls();status('Simulating payment — no money moves…');
  try{activeSale=await api(`/api/sales/${encodeURIComponent(activeSale.sale_id)}/simulate-payment`,{});
    renderReceipt(activeSale);status('SIMULATED PAID. No financial settlement or inventory change occurred.');}
  catch(e){status(e.message,true);}finally{busy=false;setControls();}
});
$('print').addEventListener('click',()=>window.print());
async function start(){
  try{const [state,items]=await Promise.all([api('/api/status'),api('/api/catalog')]);
    if(state.mode!=='DEMO_ONLY'||state.payments!=='SIMULATED_ONLY')throw new Error('UNEXPECTED_LIVE_MODE');
    catalog=items.items;$('connection').textContent='Local · Connected';renderCatalog();renderCart();
    status('Demo checkout ready. Payments and inventory are disconnected.');}
  catch(e){$('connection').textContent='Unavailable';status(e.message,true);}
}
start();
