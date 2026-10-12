/* Actual browser/installed-Core test only: no mocked successful responses. */
const {chromium}=require('playwright');const {spawn}=require('child_process');const fs=require('fs');const path=require('path');const crypto=require('crypto');const os=require('os');
const root=path.resolve(__dirname,'..');const evidence=process.env.UI01_EVIDENCE_DIR;
if(!evidence||!path.isAbsolute(evidence)){console.error('Set UI01_EVIDENCE_DIR to a new absolute external evidence directory');process.exit(2);}
if(fs.existsSync(evidence)){console.error('Evidence directory already exists; preserve prior evidence');process.exit(2);}fs.mkdirSync(evidence,{recursive:true});
(async()=>{
 const checks=[],errors=[];let browser,server;let serverStderr='';
 try{
  browser=await chromium.launch({headless:true,executablePath:chromium.executablePath()});
  if(browser.version()!=='151.0.7922.34')throw Error('LOCKED_BROWSER_VERSION_MISMATCH:'+browser.version());
  const workspace=path.join(os.tmpdir(),'skate-ui01-demo-browser-'+crypto.randomUUID());
  server=spawn(process.env.UI01_PYTHON||'python3',[path.join(root,'adapter/bridge.py'),'--new-workspace',workspace,'--seed-synthetic'],{stdio:['ignore','pipe','pipe']});
  server.stderr.on('data',d=>{serverStderr+=d;});
  const startup=await new Promise((resolve,reject)=>{let s='';const timer=setTimeout(()=>reject(new Error('SERVER_START_TIMEOUT')),15000);server.stdout.on('data',d=>{s+=d;try{const value=JSON.parse(s.trim());clearTimeout(timer);resolve(value);}catch{}});server.on('exit',code=>{clearTimeout(timer);reject(new Error('SERVER_EXIT:'+code));});});
  const page=await browser.newPage({viewport:{width:1280,height:900}});page.on('pageerror',e=>errors.push(e.message));
  await page.goto(startup.origin);await page.getByText('Actual Core · synthetic',{exact:true}).waitFor();checks.push('UIB01_runtime_ready');
  await page.locator('#scan-id').fill('SKT-0900-L');await page.locator('#scan-id').press('Enter');await page.locator('#detail dd').filter({hasText:'SKT-0900'}).waitFor();checks.push('UIB02_keyboard_scan_detail');
  await page.locator('#destination').selectOption('LOC-STORAGE');await page.locator('#move').click();await page.locator('#detail dd').filter({hasText:'LOC-STORAGE'}).waitFor();checks.push('UIB03_mutation_projection_refresh');
  await page.locator('[data-view="audit"]').click();await page.locator('#receipt').filter({hasText:'LOCATION_TRANSFERRED'}).waitFor({timeout:1500}).catch(()=>{});
  if(!await page.locator('#receipt').textContent().then(t=>t.includes('ACCEPTED')&&t.includes('event_ids')))throw Error('MISSING_RECEIPT');checks.push('UIB04_receipt');
  await page.locator('[data-view="rental"]').click();if(!await page.getByRole('button',{name:'Checkout pair',exact:true}).isDisabled())throw Error('GATED_CONTROL_ACTIVE');checks.push('UIB05_gated_controls');
  await page.locator('[data-view="runtime"]').click();await page.locator('#health-state').filter({hasText:'HEALTHY'}).waitFor();checks.push('UIB06_navigation_health');
  await page.locator('[data-view="inventory"]').click();await page.locator('#filter').fill('NO-MATCH');await page.locator('#empty').waitFor();checks.push('UIB07_empty_filter');await page.locator('#filter').fill('');
  await page.locator('#scan-id').fill('NO-ASSET');await page.locator('#scan-id').press('Enter');await page.locator('#message').filter({hasText:'ASSET_NOT_FOUND'}).waitFor();checks.push('UIB08_error_receipt');
  await page.locator('#scan-id').focus();if(!await page.locator('#scan-id').evaluate(e=>e.matches(':focus-visible')))throw Error('FOCUS_NOT_VISIBLE');checks.push('UIB09_focus');
  await page.screenshot({path:path.join(evidence,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('MOBILE_OVERFLOW');await page.screenshot({path:path.join(evidence,'mobile.png'),fullPage:true});checks.push('UIB10_responsive_render');
  await stopServer(server);await page.locator('#refresh').click();await page.locator('#connection').filter({hasText:'Unavailable'}).waitFor();checks.push('UIB11_runtime_unavailable');
  if(errors.length)throw Error('PAGE_ERRORS:'+errors.join(','));
  const screenshots=Object.fromEntries(['desktop.png','mobile.png'].map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(evidence,name))).digest('hex')]));
  fs.writeFileSync(path.join(evidence,'BROWSER_RESULT.json'),JSON.stringify({status:'PASS_OPERATOR_MEASUREMENT_NOT_JUDGE',checks,case_count:checks.length,errors,skips:0,browser_launched:true,browser_version:browser.version(),browser_executable:chromium.executablePath(),browser_executable_sha256:crypto.createHash('sha256').update(fs.readFileSync(chromium.executablePath())).digest('hex'),screenshots,source_hashes:Object.fromEntries(['frontend/app.js','frontend/adapter.js','frontend/index.html','frontend/app.css','tests/browser_smoke.cjs'].map(name=>[name,crypto.createHash('sha256').update(fs.readFileSync(path.join(root,name))).digest('hex')])),environment:{node:process.version,platform:process.platform,playwright:require('playwright/package.json').version},mode:'ACTUAL_CORE_SYNTHETIC_ONLY',startup,serverStderr,independent_verdict:false,visual_review:'REQUIRES_OPERATOR_INSPECTION'},null,2));
 }catch(e){fs.mkdirSync(evidence,{recursive:true});fs.writeFileSync(path.join(evidence,'BROWSER_RESULT.json'),JSON.stringify({status:browser?'FAILED':'NOT_RUN_BLOCKED',checks,errors,error:e.message,browser_launched:!!browser,browser_version:browser?.version(),screenshots_generated:fs.existsSync(path.join(evidence,'desktop.png')),serverStderr,independent_verdict:false},null,2));process.exitCode=2;}
 finally{if(server)await stopServer(server);if(browser)await browser.close();}
})();
function stopServer(server){return new Promise(resolve=>{if(server.exitCode!==null||server.signalCode!==null)return resolve();let done=false;const finish=()=>{if(done)return;done=true;clearTimeout(timer);resolve();};const timer=setTimeout(()=>{server.kill('SIGKILL');finish();},5000);server.once('exit',finish);server.kill('SIGINT');});}
