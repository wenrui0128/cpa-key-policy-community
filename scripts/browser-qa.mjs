// Synthetic-only screenshots. Install playwright 1.55+ beside this script.
// QUOTA_SOURCE points to the source tree. Credentials are temporary test data.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
const source=path.resolve(process.env.QUOTA_SOURCE||'.');
const output=path.resolve(process.env.QA_OUTPUT||path.join(source,'docs/images'));
const tmp=await fs.mkdtemp(path.join(os.tmpdir(),'quota-browser-'));
const password=crypto.randomBytes(32).toString('base64url'),salt=crypto.randomBytes(16).toString('hex'),iterations=300000;
const auth={username:'viewer',salt,iterations,digest:crypto.pbkdf2Sync(password,Buffer.from(salt,'hex'),iterations,32,'sha256').toString('hex')};
await fs.mkdir(output,{recursive:true});
await fs.writeFile(path.join(tmp,'loopback-auth.json'),JSON.stringify(auth),{mode:0o600});
await fs.writeFile(path.join(tmp,'public-session.json'),JSON.stringify({days:30}),{mode:0o600});
await fs.writeFile(path.join(tmp,'public-session-secret'),crypto.randomBytes(64),{mode:0o600});
// Choose a free loopback port, never replace an existing service.
const net=await import('node:net');
const probe=net.createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));
const monitor=spawn('python3',[path.join(source,'monitor/app.py')],{env:{...process.env,DATA_DIR:tmp,DEMO_MODE:'true',BIND:'127.0.0.1',PORT:String(port)},stdio:'ignore'});
let browser;
const report={synthetic_data:true,viewports:[],checks:[],screenshots:[],page_errors:[]};
try {
  const base=`http://127.0.0.1:${port}`;
  for(let i=0;i<80;i++){try{if((await fetch(base+'/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,100));}
  assert.equal((await fetch(base+'/api/state')).status,401);
  browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
  const context=await browser.newContext({httpCredentials:{username:'viewer',password},locale:'zh-CN',reducedMotion:'reduce'});
  const page=await context.newPage();page.on('pageerror',e=>report.page_errors.push(e.message));
  await page.goto(base);await page.waitForSelector('.key');
  assert.equal(await page.locator('.key').count(),6);
  async function layout(width,height){
    await page.setViewportSize({width,height});await page.waitForTimeout(80);
    const check=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,refresh:document.querySelector('#refresh').getBoundingClientRect().height,motion:getComputedStyle(document.querySelector('.end-pixel')).animationName}));
    assert(check.scroll<=check.width,`Horizontal overflow at ${width}`);assert(check.refresh>=44);assert.equal(check.motion,'none');report.viewports.push({width,height,overflow:false});
  }
  for(const [w,h] of [[320,800],[375,812],[390,844],[719,800],[844,390],[1080,900],[1280,1000]])await layout(w,h);
  await page.setViewportSize({width:1280,height:1080});await page.screenshot({path:path.join(output,'monitor-desktop.png'),fullPage:true});report.screenshots.push('monitor-desktop.png');
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(output,'monitor-mobile.png'),fullPage:true});report.screenshots.push('monitor-mobile.png');
  const initial=await (await context.request.get(base+'/api/state')).json();
  let fixture=structuredClone(initial);
  await page.route('**/api/state',route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(fixture)}));
  fixture.plugin.keys[0].name='\"><img src=x onerror="window.injected=true">';
  await page.locator('#refresh').click();await page.waitForTimeout(150);
  assert.equal(await page.locator('.keyname').first().textContent(),fixture.plugin.keys[0].name);
  assert.equal(await page.locator('.key img').count(),0);assert.equal(await page.evaluate(()=>window.injected),undefined);
  report.checks.push('key-label-text-and-attribute-escaping');
  for(const [cards,text] of [[{available_count:0,expirations:[],ok:true},'0 张'],[{available_count:null,expirations:[],ok:false,error:'Waiting'},'待确认'],[{available_count:3,unknown_expiry_count:1,expirations:[],ok:false,error:'保留上次确认'},'3 张']]){
    fixture.reset_cards=cards;await page.locator('#refresh').click();await page.waitForTimeout(100);assert((await page.locator('#reset-card-count').textContent()).includes(text));
  }
  report.checks.push('zero-unknown-and-stale-reset-cards');
  fixture=structuredClone(initial);fixture.status.official_ok=false;fixture.status.official_error='上游暂不可用，保留最后确认额度';
  await page.locator('#refresh').click();await page.waitForTimeout(100);assert.equal(await page.locator('#official-percent').textContent(),'62.0%');assert.equal(await page.locator('#official-status').textContent(),'上次确认值');
  report.checks.push('stale-official-display');
  await page.unroute('**/api/state');await page.route('**/api/state',r=>r.abort());await page.locator('#refresh').click();await page.waitForTimeout(150);assert.equal(await page.locator('.key').count(),6);assert((await page.locator('#errors').textContent()).includes('保留上次画面'));report.checks.push('network-failure-keeps-last-view');
  // Capture plugin UI only after authenticating to the disposable CPA instance.
  if(process.env.CPA_QA_BASE){
    const plugin=await context.newPage();plugin.on('pageerror',e=>report.page_errors.push(e.message));
    await plugin.route('**/v0/management/plugins/cpa-key-policy/keys',async route=>{
      if(route.request().method()!=='GET')return route.continue();
      const response=await route.fetch();const body=await response.json();
      body.keys=body.keys.filter(k=>k.id!=='new-synthetic').map(k=>{const fake=initial.plugin.keys.find(x=>x.id===k.id);return fake?{...k,usage:{...k.usage,...fake.usage}}:k;});
      await route.fulfill({response,json:body});
    });
    await plugin.setViewportSize({width:1280,height:1000});
    await plugin.goto(process.env.CPA_QA_BASE+'/v0/resource/plugins/cpa-key-policy/index.html');
    await plugin.locator('input[type=password]').fill(process.env.CPA_QA_SECRET);await plugin.locator('button[type=submit]').click();
    await plugin.waitForSelector('input[type=number]',{timeout:10000});
    await plugin.waitForTimeout(300);assert.equal(await plugin.locator('input[type=password]').count(),0);
    await plugin.screenshot({path:path.join(output,'plugin-desktop.png'),fullPage:true});report.screenshots.push('plugin-desktop.png');
    report.checks.push('plugin-weekly-management-page');
  }
  assert.deepEqual(report.page_errors,[]);report.checks.push('no-browser-exceptions','reduced-motion','touch-target','anonymous-api-401');
  await fs.writeFile(path.join(output,'../browser-validation.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
} finally {
  if(browser)await browser.close();monitor.kill('SIGTERM');await new Promise(r=>monitor.once('exit',r));await fs.rm(tmp,{recursive:true,force:true});
}
