// Phase 23: ETFs im Reiter Börse (nur Anzeige, noch nicht kaufbar).
function etfName(def){if(def.kind==='region')return 'ETF '+(REGION[def.key]||def.key);if(def.kind==='category')return 'ETF '+({beer:'Bier',wine:'Wein',spirits:'Spirituosen',softdrinks:'Softdrinks',water:'Wasser'}[def.key]||def.key);return 'ETF '+fmGroupLabel(def.key)}
function etfWeights(def,i){
 const weights=D.etfs?.weights?.[def.id]?.[i]||[];
 return weights.map(([id,weight])=>({id,weight})).sort((a,b)=>b.weight-a.weight)
}
function etfsOf(firmId){return D.etfs?D.etfs.definitions.filter(def=>def.members.includes(firmId)):[]}
function etfMembership(firmId){const defs=etfsOf(firmId);return defs.length?'<p class="hint">Enthalten in: '+defs.map(def=>esc(etfName(def))).join(', ')+'</p>':''}
function etfRow(def,points){
 const levels=D.etfs.levels[def.id]||[];
 let first=null,last=null;
 points.forEach(i=>{const value=levels[i];if(value==null)return;if(first===null)first=i;last=i});
 const firms=first===null?0:(D.etfs.members?.[def.id]?.[last]??0),level=first===null?null:levels[last];
 const change=level!=null&&levels[first]>0?level/levels[first]-1:null,top=first===null?null:etfWeights(def,last)[0];
 return '<tr class="click" tabindex="0" data-etf="'+esc(def.id)+'"><td>'+esc(etfName(def))+'</td><td class="num" data-value="'+firms+'">'+nf(firms,0)+'</td><td class="num" data-value="'+(level==null?'':level)+'">'+(level==null?'–':nf(level,2))+'</td><td class="num" data-value="'+(change==null?'':change*100)+'">'+(change==null?'–':pct(change))+'</td><td>'+(top?actorLabel(top.id)+' ('+pct(top.weight)+')':'–')+'</td></tr>'
}
function renderEtfs(){
 try{renderStockExplorer()}catch(err){console.error(err)}
 try{renderEtfBrowser()}catch(err){console.error(err)}
 const chips=[['region','Regionen'],['category','Kategorien'],['stage','Branchen (Stufen)']];
 let kind=S.etfKind||store.get('etf-kind','region');
 if(!chips.some(chip=>chip[0]===kind))kind='region';
 S.etfKind=kind;
 $('#etf-kind').innerHTML=chips.map(chip=>'<button class="chip" data-kind="'+chip[0]+'" aria-pressed="'+(chip[0]===kind?'true':'false')+'">'+chip[1]+'</button>').join('');
 $('#etf-kind').onclick=e=>{const btn=e.target.closest('button[data-kind]');if(!btn)return;S.etfKind=btn.dataset.kind;store.set('etf-kind',btn.dataset.kind);renderEtfs()};
 if(!D.etfs){$('#etf-table').innerHTML='<tbody><tr><td>'+empty('Dieser Lauf enthält keine ETFs.')+'</td></tr></tbody>';$('#etf-members').innerHTML='';return}
 const defs=D.etfs.definitions.filter(def=>def.kind===kind).sort((a,b)=>etfName(a).localeCompare(etfName(b))),points=stockPoints('week');
 chart('etf-chart',{type:'line',data:{labels:points.map(i=>stockLabel(i,'week')),datasets:defs.map((def,j)=>stockDataset(etfName(def),stockNormal(points.map(i=>D.etfs.levels[def.id]?.[i]??null)),pal()[j%8]))},options:stockOptions(points,'week')});
 if(!defs.some(def=>def.id===S.etfOpen))S.etfOpen=defs.length?defs[0].id:null;
 $('#etf-table').innerHTML='<thead><tr><th>Name</th><th>Firmen</th><th>Stand</th><th>Rendite im Zeitraum</th><th>Grösste Firma</th></tr></thead><tbody>'+(defs.length?defs.map(def=>etfRow(def,points)).join(''):'<tr><td colspan="5">'+empty('Keine ETFs in dieser Gruppe.')+'</td></tr>')+'</tbody>';
 $$('#etf-table tr[data-etf]').forEach(row=>{const open=()=>{S.etfOpen=row.dataset.etf;renderEtfMembers()};row.onclick=open;row.onkeydown=e=>{if(e.key==='Enter')open()}});
 renderEtfMembers()
}
function renderEtfMembers(){
 const target=$('#etf-members');
 $$('#etf-table tr[data-etf]').forEach(row=>row.setAttribute('aria-selected',row.dataset.etf===S.etfOpen?'true':'false'));
 const def=D.etfs?.definitions.find(d=>d.id===S.etfOpen);
 if(!def){target.innerHTML='';return}
 const points=stockPoints('week'),levels=D.etfs.levels[def.id]||[];
 let last=null;points.forEach(i=>{if(levels[i]!=null)last=i});
 target.innerHTML='<h3>Mitglieder: '+esc(etfName(def))+'</h3>'+(last===null?empty('Im Zeitraum ohne Kurs.'):'<div class="table-wrap"><table id="etf-member-table"><thead><tr><th>Firma</th><th>Gewicht</th><th>Kurs</th></tr></thead><tbody>'+etfWeights(def,last).map(entry=>{const price=D.stocks.prices[entry.id]?.[last];return '<tr><td><a href="#firms" data-firm="'+esc(entry.id)+'">'+actorLabel(entry.id)+'</a></td><td class="num" data-value="'+entry.weight*100+'">'+pct(entry.weight)+'</td><td class="num" data-value="'+(price==null?'':price)+'">'+(price==null?'–':nf(price,2)+' CHF')+'</td></tr>'}).join('')+'</tbody></table></div>');
 wireFirmLinks(target)
}

// Karte «ETFs»: links alle ETFs, rechts die Mitglieder des gewählten ETFs mit Zeiträumen.
function etfPeriods(def){
 const weights=D.etfs?.weights?.[def.id]||[],years=D.stocks?.years||[],n=Math.min(weights.length,years.length),byFirm=new Map();
 for(let i=0;i<n;i++)(weights[i]||[]).forEach(entry=>{
  const id=entry[0],list=byFirm.get(id)||[],cur=list[list.length-1];
  if(cur&&cur.lastIdx===i-1){cur.lastIdx=i;cur.to=years[i];cur.weight=entry[1]}
  else list.push({firstIdx:i,lastIdx:i,from:years[i],to:years[i],weight:entry[1]});
  byFirm.set(id,list)});
 return {byFirm,lastIdx:n-1}}
function etfCurrentCount(def){
 const members=D.etfs?.members?.[def.id]||[];return members.length?(members[members.length-1]||0):0}
function renderEtfBrowser(){
 const old=document.getElementById('etf-chart')?.closest('.card');if(old)old.style.display='none';
 const card=exEnsureCard('etf-browser',document.getElementById('etf-chart'),'<h3>ETFs</h3><p class="hint">Körbe von Aktien, nur zur Anzeige (noch nicht kaufbar). Links einen ETF wählen, rechts stehen seine Mitglieder mit Zeitraum und Gewicht. Ein Klick auf eine Firma öffnet ihre Details.</p><div class="etf-grid" style="display:grid;grid-template-columns:300px minmax(0,1fr);gap:14px;align-items:start"><div id="etfb-list" style="max-height:520px;overflow-y:auto;border:1px solid var(--border,#ccc);border-radius:6px"></div><div id="etfb-members"></div></div><style>@media (max-width:800px){#etf-browser .etf-grid{grid-template-columns:1fr!important}}#etf-browser .ex-row{display:flex;justify-content:space-between;gap:8px;width:100%;padding:5px 8px;border:0;background:none;text-align:left;cursor:pointer;color:inherit;font:inherit}#etf-browser .ex-row:hover{background:rgba(128,128,128,.12)}#etf-browser .ex-row.active{background:rgba(60,120,220,.22);font-weight:600}#etf-browser .ex-gh{padding:4px 8px;font-weight:700;font-size:12px;background:rgba(128,128,128,.15);position:sticky;top:0}</style>');
 if(!card)return;
 if(!D.etfs||!D.etfs.definitions.length){card.style.display='';card.querySelector('#etfb-list').innerHTML='<p class="hint" style="padding:8px">Dieser Lauf enthält keine ETFs.</p>';card.querySelector('#etfb-members').innerHTML='';return}
 const defs=D.etfs.definitions.slice().sort((a,b)=>etfName(a).localeCompare(etfName(b)));
 let sel=S.etfBrowse||store.get('etf-browse',null);if(!defs.some(d=>d.id===sel))sel=defs[0].id;
 S.etfBrowse=sel;
 const drawList=()=>{card.querySelector('#etfb-list').innerHTML=defs.map(def=>'<button class="ex-row'+(def.id===sel?' active':'')+'" data-etf-sel="'+esc(def.id)+'"><span>'+esc(etfName(def))+'</span><span style="white-space:nowrap">'+nf(etfCurrentCount(def),0)+' Firmen</span></button>').join('')};
 const drawMembers=()=>{
  const def=defs.find(d=>d.id===sel),target=card.querySelector('#etfb-members'),info=etfPeriods(def),firmIds=[...info.byFirm.keys()];
  if(!firmIds.length){target.innerHTML='<h3>'+esc(etfName(def))+'</h3>'+empty('Dieser ETF hatte noch nie genug Mitglieder.');return}
  const rows=firmIds.map(id=>{const list=info.byFirm.get(id),stillIn=list[list.length-1].lastIdx===info.lastIdx,lastW=list[list.length-1].weight;
   const text=list.map((p,k)=>{const end=(k===list.length-1&&stillIn)?'bis heute':'bis Jahr '+p.to;return 'von Jahr '+p.from+' '+end}).join('; ');
   return {id,text,stillIn,weight:lastW,start:list[0].from}}).sort((a,b)=>(b.stillIn-a.stillIn)||(b.weight-a.weight));
  target.innerHTML='<h3>Mitglieder: '+esc(etfName(def))+'</h3><div class="table-wrap"><table id="etfb-table"><thead><tr><th>Firma</th><th>Zeitraum</th><th>Gewicht</th></tr></thead><tbody>'+rows.map(r=>'<tr><td><a href="#firms" data-firm="'+esc(r.id)+'">'+actorLabel(r.id)+'</a></td><td data-value="'+r.start+'">'+esc(r.text)+'</td><td class="num" data-value="'+(r.weight*100)+'">'+(r.stillIn?pct(r.weight):'–')+'</td></tr>').join('')+'</tbody></table></div><p class="hint">Gewicht: aktuelles Gewicht im ETF (nur für heutige Mitglieder).</p>';
  wireFirmLinks(target)};
 card.querySelector('#etfb-list').onclick=e=>{const b=e.target.closest('button[data-etf-sel]');if(!b)return;sel=b.dataset.etfSel;S.etfBrowse=sel;store.set('etf-browse',sel);drawList();drawMembers()};
 card.style.display='';drawList();drawMembers()}
