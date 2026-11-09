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
 let h='<section class="hg-card holding-block" id="hg-g-'+prefix+'-'+esc(g.holding)+'"><h4>'+(typeof firm==='function'&&firm(g.holding)?hgFirmLink(g.holding,g.name):esc(g.name))+'</h4>';
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
