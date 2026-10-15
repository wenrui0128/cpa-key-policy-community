let DISPLAY={estimated_total:1000,time_zone:'UTC'};
const $=id=>document.getElementById(id),money=v=>v==null?'—':'$'+Number(v).toFixed(2),esc=v=>{let e=document.createElement('span');e.textContent=String(v??'');return e.innerHTML.replaceAll('"','&quot;').replaceAll("'",'&#39;')};
const date=v=>{let d=new Date(typeof v==='number'?v*1000:v);return !v||d.getFullYear()<2000?'—':d.toLocaleString('zh-CN',{timeZone:DISPLAY.time_zone,month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})};
function countdown(v){let n=(typeof v==='number'?v*1000:Date.parse(v))-Date.now();if(!Number.isFinite(n))return '等待确认';if(n<=0)return '等待新周期';let h=Math.floor(n/36e5),d=Math.floor(h/24);return d?`${d}天 ${h%24}小时`:`${h}小时 ${Math.floor(n/6e4)%60}分`}
function tint(card,p){card.dataset.quotaBand=p<20?'low':p<=50?'medium':'high';card.classList.toggle('low',p<20)}
function endPixels(){document.querySelectorAll('.key>.track,.codex>.track').forEach(track=>{let fill=track.querySelector('.fill'),value=Math.max(0,Math.min(100,parseFloat(fill.style.width)||0)),pixel=track.querySelector('.end-pixel');if(!pixel){pixel=document.createElement('span');pixel.className='end-pixel';pixel.setAttribute('aria-hidden','true');track.append(pixel)}let lit=track.clientWidth*value/100;pixel.hidden=lit<=0;if(pixel.hidden)return;let left=Math.floor(Math.max(0,lit-.001)/17)*17;fill.style.maskImage=`linear-gradient(to right,#000 ${left}px,transparent ${left}px)`;pixel.style.left=left+'px';pixel.style.width=Math.min(12,lit-left)+'px';let severity=1-value/100;pixel.style.setProperty('--blink-period',(4-3.2*severity).toFixed(2)+'s');pixel.style.setProperty('--blink-low',(0.75-0.6*severity).toFixed(2));pixel.style.setProperty('--blink-glow',(2+10*severity).toFixed(1)+'px')})}
function metric(value,label){return `<div class="metric"><strong>${esc(value)}</strong><small>${esc(label)}</small></div>`}
let lastKeySignature='';
function renderKeys(keys){
  const signature=JSON.stringify(keys);
  if(signature===lastKeySignature){document.querySelectorAll('.key .reset strong').forEach((el,i)=>{el.textContent=countdown(keys[i]?.usage?.weekly_reset_at)});return;}
  lastKeySignature=signature;
  $('key-count').textContent=String(keys.length).padStart(2,'0')+' KEYS / WEEKLY';
  $('keys').innerHTML=keys.map(k=>{
    const u=k.usage||{},limit=Number(k.weekly_limit_usd||0),remain=limit?Math.max(0,limit-Number(u.weekly_usd||0)):null,p=limit?Math.min(100,remain/limit*100):100;
    const hit=Number(u.weekly_cache_read_tokens||0),input=Number(u.weekly_input_tokens||0);
    return `<article class="key" data-p="${p}">
      <div class="keyhead"><div class="keyname">${esc(k.name||k.id)}</div><span class="key-state">${k.enabled?'':'已停用'}</span></div>
      <div class="keybudget"><div><small class="budget-caption">剩余额度</small><strong class="money">${limit?money(remain):'不限额'}</strong></div><strong class="percent">${limit?p.toFixed(0)+'%':'—'}</strong></div>
      <div class="budget-total">周预算 ${limit?money(limit):'不限额'}</div>
      <div class="track"><div class="fill" role="progressbar" aria-label="${esc(k.name||k.id)} 剩余额度" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${p.toFixed(1)}"></div></div>
      <div class="metrics">${metric(money(u.weekly_usd),'本周期消费')}${metric(money(u.daily_usd),'今日消费')}${metric(u.weekly_call_count??0,'本周期调用')}${metric(hit+input?(100*hit/(hit+input)).toFixed(1)+'%':'—','缓存命中率')}</div>
      <div class="reset"><span>重置 ${date(u.weekly_reset_at)}</span><strong>${countdown(u.weekly_reset_at)}</strong></div>
    </article>`;
  }).join('')||'<div class="empty">暂无 Key 数据</div>';
  document.querySelectorAll('.key').forEach(card=>{const p=Number(card.dataset.p);tint(card,p);card.querySelector('.fill').style.width=p+'%'});
}
function resetCardDate(value){
  const d=new Date(value*1000);
  return d.toLocaleString('zh-CN',{timeZone:DISPLAY.time_zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
}
function renderResetCards(cards){
  const known=Number.isInteger(cards?.available_count)&&cards.available_count>=0;
  const countText=known?`${cards.available_count} 张未使用的重置卡`:'重置卡数量待确认';
  if($('reset-card-count').textContent!==countText)$('reset-card-count').textContent=countText;
  const batches=(Array.isArray(cards?.expirations)?cards.expirations:[]).filter(b=>Number.isInteger(b.count)&&b.count>0&&Number.isFinite(b.expires_at)&&b.expires_at>0);
  $('reset-card-list').innerHTML=batches.map(b=>{
    const soon=b.expires_at*1000-Date.now()<3*86400000;
    return `<div class="reset-card-row"><strong>${b.count} 张</strong><div><time datetime="${new Date(b.expires_at*1000).toISOString()}">${esc(resetCardDate(b.expires_at))}</time><small>${soon?'即将过期':'到期时间'}</small></div></div>`;
  }).join('')||`<div class="reset-card-empty">${known?(cards.available_count?'有效期明细暂未提供':'暂无未使用的重置卡'):'等待有效期数据…'}</div>`;
  const missing=Number.isInteger(cards?.unknown_expiry_count)&&cards.unknown_expiry_count>0?` · ${cards.unknown_expiry_count} 张未提供有效期`:'';
  const status=cards?.ok?'CPA 已确认':cards?.error||(cards?.at?'显示上次确认值':'等待 CPA 首次查询');
  $('reset-card-note').textContent=`${esc(DISPLAY.time_zone)} · ${status}${missing}${cards?.at?' · 更新 '+date(cards.at):''}`;
}
let busy=false;async function refresh(){if(busy)return;busy=true;$('refresh').disabled=true;$('refresh').textContent='READING';const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);try{let r=await fetch('/api/state',{cache:'no-store',signal:controller.signal});if(!r.ok)throw Error('读取失败');let d=await r.json(),s=d.status,o=d.official,p=d.plugin;DISPLAY=d.display||DISPLAY;let warnings=[s.plugin_error,s.official_error,s.cycle_error].filter(Boolean);$('errors').textContent=warnings.join(' · ');$('errors').className=warnings.length?'error':'';$('report-status').textContent=warnings.length?'STATUS NEEDS ATTENTION.':'STATUS REPORT READY.';for(let [id,ok] of [['st-plugin',s.plugin_ok],['st-cpa',s.official_ok],['st-sync',s.cycle_ok]]){$(id).classList.toggle('ok',!!ok);$(id).setAttribute('aria-label',ok?'正常':'等待或异常');$(id).dataset.tip=ok?'正常':'等待或异常'}if(o){$('official-percent').textContent=o.remaining_percent.toFixed(1)+'%';$('official-estimate').textContent='估算剩余 '+money(DISPLAY.estimated_total*Math.max(0,Math.min(100,o.remaining_percent))/100)+' / 总额度 '+money(DISPLAY.estimated_total);$('official-countdown').textContent=countdown(o.reset_at);$('official-reset').textContent=date(o.reset_at);$('official-status').textContent=s.official_ok?'CPA 已确认':'上次确认值';tint($('codex'),o.remaining_percent);$('official-fill').style.width=Math.max(0,Math.min(100,o.remaining_percent))+'%';$('official-fill').setAttribute('aria-valuenow',Math.max(0,Math.min(100,o.remaining_percent)).toFixed(1))}renderResetCards(d.reset_cards);renderKeys(p.keys);$('stamp').textContent=`个人 ${date(p.at)} / 官方 ${date(o?.at)} · 每 15 秒刷新`;requestAnimationFrame(endPixels)}catch{$('errors').className='error';$('errors').textContent='读取失败，保留上次画面。请检查网络连接后刷新。';$('report-status').textContent='CONNECTION LOST / LAST SNAPSHOT.';$('reset-card-note').textContent='显示时区 · 网络读取失败，保留上次确认数据';if($('official-percent').textContent!=='—')$('official-status').textContent='上次确认值';for(const id of ['st-plugin','st-cpa','st-sync']){$(id).classList.remove('ok');$(id).setAttribute('aria-label','连接异常');$(id).dataset.tip='连接异常'}}finally{clearTimeout(timeout);busy=false;$('refresh').disabled=false;$('refresh').textContent='REFRESH'}}
$('refresh').addEventListener('click',refresh);new ResizeObserver(endPixels).observe(document.querySelector('main'));document.addEventListener('visibilitychange',()=>document.documentElement.classList.toggle('motion-hidden',document.hidden));refresh();setInterval(refresh,15000);
