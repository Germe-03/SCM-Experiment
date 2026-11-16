Object.assign(EVENT,{holding_formed:'Holding gegründet',holding_acquisition:'Tochter gekauft',holding_sweep:'Reserve abgeschöpft',holding_cover:'Holding deckt Verluste',holding_no_cover:'Holding stützt nicht',holding_sold:'Tochter verkauft',holding_takeover:'Holding gekauft',holding_dissolved:'Holding aufgelöst',holding_daughter_lost:'Tochter ausgeschieden',merger:'Fusion (Firma geht auf)',merger_formed:'Fusion',merger_blocked:'Fusion verboten'});

function holdingGroupsList(){return (D.holding_groups||[]).filter(g=>g.founded_year<=range.to&&(!g.dissolved_year||g.dissolved_year>=range.from))}
function holdingSuccessorName(id){
 if(!id)return '';
 if(typeof firm==='function'&&firm(id))return fname(id);
 const group=(D.holding_groups||[]).find(g=>String(g.holding)===String(id));
 return group?.name||fname(id)
}
(function(){if(typeof document==='undefined')return;const st=document.createElement('style');st.textContent='.hg-flash{outline:3px solid var(--accent,#2b6cb0);transition:outline .4s}.hg-card{border:1px solid var(--line,#ddd);border-radius:8px;padding:10px 12px;margin:0 0 10px}.hg-card h4{margin:0 0 4px}.hg-card .hint{margin:2px 0 6px}.hg-old{margin:6px 0}.hg-old summary{cursor:pointer}.hg-gen{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:12px}.hg-card .table-wrap{overflow:visible;border:0}.hg-card table{width:100%;table-layout:fixed;font-size:13px}.hg-card th,.hg-card td{padding:6px 8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hg-card th:first-child,.hg-card td:first-child{width:38%}';document.head.appendChild(st)})();
function hgFirmLink(id,label){
 if(typeof firm==='function'&&firm(id))return '<a href="#" class="click" data-firm="'+esc(id)+'">'+esc(label||fname(id))+'</a>';
 return '<a href="#" class="click" data-hg-goto="'+esc(id)+'">'+esc(label||holdingSuccessorName(id))+'</a>'
}
function hgGroupOf(id){return (D.holding_groups||[]).find(g=>String(g.holding)===String(id)||String(g.listing_id)===String(id))}
function hgSubGroup(id){return (D.holding_groups||[]).find(g=>(g.subs||[]).some(s=>String(s.firm)===String(id)))}
function hgGoto(holdingId,prefix){
 const g=hgGroupOf(holdingId);if(!g)return;
 const el=document.getElementById('hg-g-'+(prefix||'firms')+'-'+g.holding);if(!el)return;
 const det=el.closest('details');if(det)det.open=true;
 el.scrollIntoView({block:'center',behavior:'smooth'});el.classList.add('hg-flash');setTimeout(()=>el.classList.remove('hg-flash'),2000)
}
function hgWire(box,prefix){
 wireFirmLinks(box);
 box.querySelectorAll('[data-hg-goto]').forEach(a=>{a.onclick=e=>{e.preventDefault();e.stopPropagation();hgGoto(a.dataset.hgGoto,prefix)}})
}
function hgCard(g,prefix,mode){
 const subs=g.subs||[],active=g.status==='active';
 const status=active?'aktiv seit Jahr '+esc(g.founded_year):'aufgelöst in Jahr '+esc(g.dissolved_year)+(g.successor?', Nachfolger: '+hgFirmLink(g.successor):'');
 const total=subs.filter(s=>s.active).reduce((a,s)=>({r:a.r+(s.revenue??0),p:a.p+(s.profit??0)}),{r:0,p:0});
 let h='<section class="hg-card holding-block" id="hg-g-'+prefix+'-'+esc(g.holding)+'"><h4>'+(typeof firm==='function'&&firm(g.holding)?hgFirmLink(g.holding,g.name):esc(g.name))+' <button type="button" class="btn" data-hg-popup="'+esc(g.holding)+'">Diagramme</button></h4>';
 h+='<p class="hint">'+status+' · Kasse der Holding '+chf(g.cash??0)+(active?' · Töchter zusammen: Umsatz '+chf(total.r)+', Gewinn '+chf(total.p):'')+'</p>';
 if(mode==='stocks'){
  h+='<p class="hint">Kürzel '+esc(fname(g.listing_id))+' (Kurs wird als Holding fortgeführt)</p>';
  if(hasStockPrices(g.listing_id))h+='<button class="btn" data-hg-stock="'+esc(g.listing_id)+'">Kurs vergleichen</button> '
 }
 if(subs.length){
  h+='<div class="table-wrap"><table><thead><tr><th>Tochter</th><th class="num">Umsatz</th><th class="num">Gewinn</th><th class="num">Kasse</th></tr></thead><tbody>'+subs.map(s=>'<tr class="click" data-firm="'+esc(s.firm)+'"><td>'+esc(s.name)+(s.active?'':' <span class="hint">(ausgeschieden)</span>')+'</td><td class="num">'+chf(s.revenue??0)+'</td><td class="num">'+chf(s.profit??0)+'</td><td class="num" title="Reserve '+esc(chf(s.reserve??0))+', Mindestreserve '+esc(chf(s.reserve_floor??0))+'">'+chf(s.cash??0)+'</td></tr>').join('')+'</tbody></table></div>'
 }else h+='<p class="hint">Keine Töchter.</p>';
 return h+'</section>'
}
function holdingTable(groups,mode,prefix){
 if(!groups.length)return empty('In diesem Lauf ist keine Holding entstanden.');
 prefix=prefix||mode;
 const act=groups.filter(g=>g.status==='active'),old=groups.filter(g=>g.status!=='active');
 let h='';
 if(act.length)h+='<div class="hg-gen">'+act.map(g=>hgCard(g,prefix,mode)).join('')+'</div>';
 else h+='<p class="hint">Keine aktive Holding im gewählten Zeitraum.</p>';
 if(old.length)h+='<details class="hg-old"><summary>Aufgelöste Holdings ('+old.length+')</summary>'+old.map(g=>hgCard(g,prefix,mode)).join('')+'</details>';
 return h
}
function renderHoldingGroups(boxId,mode){
 const box=$('#'+boxId);
 if(!box)return;
 if(mode==='compare'){box.innerHTML='';return}
 box.innerHTML='<div class="card wide"><h3>Holdings und Töchter</h3><p class="hint">Klicke auf einen Namen, um die Firma zu öffnen.</p>'+holdingTable(holdingGroupsList(),mode,mode)+'</div>';
 hgWire(box,mode);
 box.querySelectorAll('button[data-hg-stock]').forEach(button=>{button.onclick=()=>{addStock(button.dataset.hgStock)}})
}
function wrapHoldingView(tab,mode,box){
 const old=VIEWS[tab];
 VIEWS[tab]=()=>{if(typeof old==='function')old();renderHoldingGroups(box,mode)}
}
if(typeof VIEWS!=='undefined')[['firms','firms','hg-firms'],['compare','compare','hg-compare'],['stocks','stocks','hg-stocks']].forEach(args=>wrapHoldingView(...args));

// Firmendetail: Hinweis auf Mutter bzw. Töchter mit Links.
function hgDetailNote(id){
 const mother=hgSubGroup(id),own=(D.holding_groups||[]).find(g=>String(g.holding)===String(id)||String(g.listing_id)===String(id));
 const parts=[];
 if(mother)parts.push('Gehört zu Holding '+(typeof firm==='function'&&firm(mother.holding)?hgFirmLink(mother.holding,mother.name):'<a href="#" class="click" data-hg-goto="'+esc(mother.holding)+'">'+esc(mother.name)+'</a>')+(mother.status==='active'?'':' (aufgelöst)')+'.');
 if(own){const subs=own.subs||[];parts.push('Töchter: '+(subs.length?subs.map(s=>hgFirmLink(s.firm,s.name)).join(', '):'keine')+'.')}
 return parts.join(' ')
}
if(typeof renderFirmDetail==='function'){
 const baseDetail=renderFirmDetail;
 renderFirmDetail=function(){
  baseDetail.apply(this,arguments);
  const root=$('#fm-detail'),id=S.fmFirm;
  if(!root||S.tab!=='firms'||!id||String(id).includes(':')||!firm(id))return;
  const note=hgDetailNote(id);if(!note)return;
  const head=root.querySelector('.detail-head'),el=document.createElement('p');
  el.className='hint hg-note';el.innerHTML=note;
  if(head)head.insertAdjacentElement('afterend',el);else root.prepend(el);
  hgWire(el,'firms')
 }
}

// Phase 43: im Vergleich laufen die Linien der alten Firmen in die neue Firma zusammen.
function addMergerLines(cfg){
 const key=S.cmpMetric,labels=cfg.data.labels||[],extra=[];
 const parentsOf=(id,seen=new Set())=>{const m=(D.mergers||[]).find(x=>x.new===id);if(!m||seen.has(id))return [];seen.add(id);return m.parents.flatMap(p=>[{id:p,year:m.year,into:id},...parentsOf(p,seen)])};
 for(const id of S.cmp){
  const idx=cfg.data.datasets.findIndex(d=>d.label===fname(id)),ds=cfg.data.datasets[idx];
  if(!ds)continue;
  for(const p of parentsOf(id)){
   const f=firm(p.id);if(!f)continue;
   const into=(D.mergers||[]).find(x=>x.new===p.into),target=cfg.data.datasets.find(d=>d.label===fname(p.into));
   const data=labels.map(y=>y<=p.year?(f.yearly.find(r=>r.year===y)?.[key]??null):(y===p.year+1?(target?.data[labels.indexOf(y)]??null):null));
   extra.push({label:f.name+' (vor Fusion)',data,borderColor:ds.borderColor,borderDash:[5,4],pointRadius:0,borderWidth:1.5,spanGaps:false})
  }
 }
 cfg.data.datasets.push(...extra)
}
if(typeof chart==='function'){const baseChart=chart;chart=function(id,cfg){if(id==='cp-metric'&&!S.cmpRelative&&typeof addMergerLines==='function')addMergerLines(cfg);return baseChart(id,cfg)}}


// Popup einer Holding: zusammengezählte Diagramme über Stammfirma und alle Töchter.
var hgPopupCharts=[];
var hgPopupScroll=null;
function hgPopupClose(){hgPopupCharts.forEach(c=>{try{c.destroy()}catch(e){}});hgPopupCharts=[];const m=document.getElementById('hg-popup');if(m)m.remove();if(hgPopupScroll){document.documentElement.style.overflow=hgPopupScroll[0];document.body.style.overflow=hgPopupScroll[1];hgPopupScroll=null}}
function hgPopupChart(id,cfg){const el=document.getElementById(id);if(!el||!window.Chart)return;const c=new Chart(el,cfg);hgPopupCharts.push(c)}
function openHoldingPopup(hid){
 hgPopupClose();
 const g=(D.holding_groups||[]).find(x=>String(x.holding)===String(hid));if(!g)return;
 const ids=[...new Set([g.listing_id,...(g.subs||[]).map(x=>x.firm)])].filter(id=>typeof firm==='function'&&firm(id));
 const years=[...new Set(ids.flatMap(id=>firm(id).yearly.map(r=>r.year)))].filter(y=>typeof inRange!=='function'||inRange(y)).sort((a,b)=>a-b);
 const val=(id,y,k)=>{const r=firm(id).yearly.find(r=>r.year===y);return r&&r[k]!=null?+r[k]:null};
 const sum=k=>years.map(y=>ids.reduce((a,id)=>a+(val(id,y,k)||0),0));
 const pal_=typeof pal==='function'?pal():['#4e79a7','#f28e2b','#e15759','#76b7b2','#59a14f','#edc948','#b07aa1','#ff9da7'];
 const col=i=>i<pal_.length?pal_[i]:'hsl('+Math.round((i*137.5)%360)+',60%,55%)';
 const groupsByStage={};ids.forEach(id=>{const f=firm(id),k=(typeof stageLabel==='function'?stageLabel(f):f.stage)||'Andere';(groupsByStage[k]=groupsByStage[k]||[]).push(id)});
 const fmtChf=v=>typeof chf==='function'?chf(v):v;const fmtPct=v=>typeof pct==='function'?pct(v):v;
 const lastY=years.at(-1),rev=sum('revenue'),prof=sum('profit'),cash=sum('cash');
 const kp=(l,v)=>'<div class="kpi"><span>'+l+'</span><b>'+v+'</b></div>';
 const m=document.createElement('div');m.id='hg-popup';
 m.style.cssText='position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.6);overflow:auto;overscroll-behavior:contain;padding:24px 16px';hgPopupScroll=[document.documentElement.style.overflow,document.body.style.overflow];document.documentElement.style.overflow='hidden';document.body.style.overflow='hidden';
 m.innerHTML='<div class="card" style="max-width:1200px;margin:0 auto;background:var(--card,var(--bg,#1b1f24))"><div class="detail-head"><button class="btn" data-hg-close aria-label="Schliessen">✕</button><h2>'+esc(g.name)+'</h2><span class="badge">'+(g.status==='active'?'aktiv seit Jahr '+g.founded_year:'aufgelöst Jahr '+g.dissolved_year)+'</span></div>'
  +'<div class="kpis">'+kp('Kasse der Holding',fmtChf(g.cash))+kp('Firmen in der Gruppe',ids.length)+kp('Umsatz Jahr '+(lastY??''),fmtChf(rev.at(-1)))+kp('Gewinn Jahr '+(lastY??''),fmtChf(prof.at(-1)))+kp('Cash aller Firmen',fmtChf(cash.at(-1)))+'</div>'
  +'<p class="hint">Summe über '+ids.map(id=>esc(firm(id).name)).join(', ')+'. Zusammensetzung wie am Ende der Simulation.</p>'
  +'<div class="grid">'
  +'<div class="card wide"><h3>Umsatz und Gewinn pro Jahr</h3><div class="chart"><canvas id="hgp-rev"></canvas></div></div>'
  +'<div class="card"><h3>Marktanteil je Stufe</h3><p class="hint">Summe der Anteile der Firmen auf dieser Stufe.</p><div class="chart"><canvas id="hgp-share"></canvas></div></div>'
  +'<div class="card"><h3>Cash je Firma (Jahresende)</h3><div class="chart"><canvas id="hgp-cash"></canvas></div></div>'
  +'<div class="card"><h3>Umsatz je Firma</h3><div class="chart"><canvas id="hgp-revf"></canvas></div></div>'
  +'<div class="card"><h3>Gewinn je Firma</h3><div class="chart"><canvas id="hgp-proff"></canvas></div></div>'
  +'<div class="card"><h3>Reputation und Qualität (Durchschnitt)</h3><div class="chart"><canvas id="hgp-rep"></canvas></div></div>'
  +(D.stocks?.prices?.[g.listing_id]?'<div class="card wide"><h3>Aktienkurs der Holding</h3><div class="chart"><canvas id="hgp-stock"></canvas></div></div>':'')
  +'</div></div>';
 document.body.appendChild(m);
 m.addEventListener('click',e=>{if(e.target===m||e.target.closest('[data-hg-close]'))hgPopupClose()});
 document.addEventListener('keydown',function esc_(e){if(e.key==='Escape'){hgPopupClose();document.removeEventListener('keydown',esc_)}});
 const base={responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:true}}};
 const axis=f=>({ticks:{callback:v=>f==='chf'?fmtChf(v):f==='pct'?fmtPct(v):v}});
 const tip=f=>({callbacks:{label:c=>c.dataset.label+': '+(f==='chf'?fmtChf(c.parsed.y):f==='pct'?fmtPct(c.parsed.y):c.parsed.y)}});
 const line=(label,data,i,extra)=>({label,data,borderColor:col(i),backgroundColor:col(i),pointRadius:0,borderWidth:2,...(extra||{})});
 const opt=f=>({...base,plugins:{...base.plugins,tooltip:tip(f)},scales:{y:axis(f)}});
 const labels=years.map(y=>'Jahr '+y);
 hgPopupChart('hgp-rev',{type:'bar',data:{labels,datasets:[{label:'Umsatz',data:rev,backgroundColor:col(0)+'99'},{type:'line',label:'Gewinn',data:prof,borderColor:col(1),backgroundColor:col(1),pointRadius:0,borderWidth:2}]},options:opt('chf')});
 hgPopupChart('hgp-share',{type:'line',data:{labels,datasets:Object.keys(groupsByStage).map((k,i)=>line(k,years.map(y=>groupsByStage[k].reduce((a,id)=>a+(val(id,y,'market_share')||0),0)),i))},options:opt('pct')});
 hgPopupChart('hgp-cash',{type:'line',data:{labels,datasets:ids.map((id,i)=>line(firm(id).name,years.map(y=>val(id,y,'cash')),i))},options:opt('chf')});
 hgPopupChart('hgp-revf',{type:'line',data:{labels,datasets:ids.map((id,i)=>line(firm(id).name,years.map(y=>val(id,y,'revenue')),i))},options:opt('chf')});
 hgPopupChart('hgp-proff',{type:'line',data:{labels,datasets:ids.map((id,i)=>line(firm(id).name,years.map(y=>val(id,y,'profit')),i))},options:opt('chf')});
 const avg=k=>years.map(y=>{const v=ids.map(id=>val(id,y,k)).filter(v=>v!=null);return v.length?v.reduce((a,b)=>a+b,0)/v.length:null});
 hgPopupChart('hgp-rep',{type:'line',data:{labels,datasets:[line('Reputation',avg('reputation'),0),line('Qualität',avg('average_quality'),1)]},options:opt('pct')});
 if(D.stocks?.prices?.[g.listing_id]&&typeof stockPoints==='function'){
  const pts=stockPoints('month'),pr=D.stocks.prices[g.listing_id];
  hgPopupChart('hgp-stock',{type:'line',data:{labels:pts.map(i=>typeof stockLabel==='function'?stockLabel(i,'month'):i),datasets:[line('Kurs in CHF',pts.map(i=>pr[i]>0?pr[i]:null),0,{spanGaps:false})]},options:{...opt('chf'),scales:{x:{ticks:{maxTicksLimit:12}},y:axis('chf')}}});
 }
}
// Auch in den Holding-Karten der Reiter Firmen und Börse: Knopf «Diagramme».
if(typeof document!=='undefined'&&document.addEventListener)document.addEventListener('click',e=>{const b=e.target.closest&&e.target.closest('[data-hg-popup]');if(b&&!b.onclick){e.preventDefault();openHoldingPopup(b.dataset.hgPopup)}});
