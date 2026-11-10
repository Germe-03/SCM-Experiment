// Aktienkurs im Reiter Vergleich und Schalter «Börsenindex einblenden» (Phase 22).
function stockIndexShown(key,fallback){return !!store.get('stock-index-'+key,fallback)}
function stockIndexSwitch(key,fallback){return '<label class="switch-line"><input type="checkbox" data-stock-index="'+key+'"'+(stockIndexShown(key,fallback)?' checked':'')+'> Börsenindex einblenden</label>'}
function wireStockIndexSwitch(root,key,onChange){const input=root.querySelector('input[data-stock-index="'+key+'"]');if(input)input.onchange=e=>{store.set('stock-index-'+key,e.target.checked);onChange()}}
function hasStockPrices(id){const prices=D.stocks?.prices?.[id];return !!prices&&stockPoints('week').some(i=>prices[i]>0)}
function stockStats(id,points){
 const prices=D.stocks.prices[id];let first=null,last=null,high=null,highYear=null,low=null,lowYear=null;
 points.forEach(i=>{const value=prices?.[i];if(value==null||value<=0)return;if(first===null)first=value;last=value;if(high===null||value>high){high=value;highYear=D.stocks.years[i]}if(low===null||value<low){low=value;lowYear=D.stocks.years[i]}});
 return first===null?null:{last,first,change:first>0?last/first-1:null,high,highYear,low,lowYear}
}
function renderCompareStock(root,ids,actorName,colorOf){
 const norm=!!store.get('cmp-stock-norm',true),withIndex=stockIndexShown('cmp',false),points=stockPoints('week'),listed=ids.filter(hasStockPrices),missing=ids.filter(id=>!listed.includes(id));
 let hint=missing.map(id=>esc(actorName(id))+' ist im gewählten Zeitraum nicht an der Börse.').join(' ');
 if(listed.length)hint+=(hint?' ':'')+'Lücken: vor dem Börsengang, nach dem Austritt und bei Banken gibt es keinen Kurs.';
 root.innerHTML='<div class="card"><h3>Aktienkurs'+(norm?' (Start = 100)':' in CHF')+'</h3><div class="filters"><label class="switch-line"><input type="checkbox" id="cp-stock-norm"'+(norm?' checked':'')+'> Start = 100</label>'+stockIndexSwitch('cmp',false)+'</div><p class="hint" id="cp-stock-hint" role="status">'+hint+'</p><div class="chart" style="height:400px"><canvas id="cp-metric"></canvas></div></div><div class="table-wrap"><table id="cp-summary"></table></div>';
 const datasets=listed.map(id=>{const raw=points.map(i=>{const value=D.stocks.prices[id][i]??null;return value!=null&&value<=0?null:value});return stockDataset(actorName(id),norm?stockNormal(raw):raw,colorOf(id))});
 if(withIndex){const idx=points.map(i=>D.stocks.index[i]>0?D.stocks.index[i]:null),dataset={...stockDataset('Börsenindex',norm?stockNormal(idx):idx,pal()[7],3),borderDash:[6,4]};if(!norm)dataset.yAxisID='y2';datasets.push(dataset)}
 const opts=stockOptions(points,'week');opts.scales.y.title={display:true,text:norm?'Start = 100':'Kurs in CHF'};
 if(withIndex&&!norm)opts.scales.y2={position:'right',grid:{display:false},title:{display:true,text:'Indexstand'},...fmtAxis()};
 chart('cp-metric',{type:'line',data:{labels:points.map(i=>stockLabel(i,'week')),datasets},options:opts});
 root.querySelector('#cp-summary').innerHTML='<thead><tr><th>Firma</th><th>Letzter Kurs</th><th>Veränderung im Zeitraum</th><th>Höchstkurs</th><th>Tiefstkurs</th></tr></thead><tbody>'+ids.map(id=>{
  const name=actorName(id),color=colorOf(id),stats=stockStats(id,points),first='<td><span class="dot" style="background:'+esc(color)+'"></span>'+esc(name)+'</td>';
  if(!stats)return '<tr>'+first+'<td colspan="4">nicht an der Börse</td></tr>';
  return '<tr>'+first+'<td class="num" data-value="'+stats.last+'">'+nf(stats.last,2)+' CHF</td><td class="num" data-value="'+(stats.change==null?'':stats.change*100)+'">'+pct(stats.change)+'</td><td class="num" data-value="'+stats.high+'">'+nf(stats.high,2)+' CHF (Jahr '+stats.highYear+')</td><td class="num" data-value="'+stats.low+'">'+nf(stats.low,2)+' CHF (Jahr '+stats.lowYear+')</td></tr>'
 }).join('')+'</tbody>';
 root.querySelector('#cp-stock-norm').onchange=e=>{store.set('cmp-stock-norm',e.target.checked);renderCompare()};
 wireStockIndexSwitch(root,'cmp',renderCompare)
}
// Grosses Auswahl-Diagramm (Index, Aktien, ETFs) im Reiter Börse.
function exColor(j){const base=pal();return j<base.length?base[j]:'hsl('+Math.round((j*137.5)%360)+',65%,50%)'}
function exEnsureCard(id,before,html){
 let card=document.getElementById(id);
 if(!card){const ref=before&&before.closest?before.closest('.card'):null;if(!ref||!ref.parentNode)return null;card=document.createElement('div');card.id=id;card.className='card wide';ref.parentNode.insertBefore(card,ref);card.innerHTML=html}
 return card}
function exGroups(){
 const s=D.stocks||{prices:{}},all=stockPoints('week');
 const stocks=Object.keys(s.prices).filter(id=>all.some(i=>s.prices[id][i]>0)).map(id=>({key:'s:'+id,id,label:stockLineName(id)})).sort((a,b)=>a.label.localeCompare(b.label));
 const etfs=D.etfs?D.etfs.definitions.map(def=>({key:'e:'+def.id,id:def.id,label:etfName(def)})).sort((a,b)=>a.label.localeCompare(b.label)):[];
 return [{id:'i',title:'Index',items:[{key:'i:index',id:'index',label:'Börsenindex'}]},{id:'s',title:'Aktien',items:stocks},{id:'e',title:'ETFs',items:etfs}]}
function exAll(){
 const g=exGroups(),idx=g[0].items[0];
 return {idx,stocks:g[1].items,etfs:g[2].items}}
function exResPoints(res){
 const w=stockPoints('week');
 if(res==='week')return w;
 if(res==='month')return stockPoints('month');
 return w.filter((i,j)=>j===w.length-1||D.stocks.years[i]!==D.stocks.years[w[j+1]])}
function exTopStocks(stocks,n){
 const w=stockPoints('week'),last=w[w.length-1],val=x=>{const p=D.stocks.prices[x.id]||[];for(let k=w.length-1;k>=0;k--){if(p[w[k]]>0)return {v:p[w[k]],at:w[k]===last}}return {v:0,at:false}};
 const r=stocks.map(x=>({x,...val(x)})).filter(o=>o.v>0);
 const live=r.filter(o=>o.at);
 return (live.length>=n?live:r).sort((a,b)=>b.v-a.v).slice(0,n).map(o=>o.x.key)}
// Rohwerte eines Eintrags auf den Punkten; Rohstoffe/Strom nur auf Jahrespunkten.
function exRaw(item,points){
 const pos=v=>v>0?v:null;
 if(item.key==='i:index')return points.map(i=>pos(D.stocks.index[i]));
 if(item.type==='s')return points.map(i=>pos(D.stocks.prices[item.id]?.[i]));
 if(item.type==='e')return points.map(i=>pos(D.etfs?.levels?.[item.id]?.[i]));
 return points.map(i=>{const r=(D.commodities||[]).find(x=>x.year===D.stocks.years[i]);if(!r)return null;const v=item.type==='c'?r.prices?.[item.id]:r.electricity?.index;return v>0?v*100:null})}
function exStats(raw){
 const v=raw.filter(x=>x!=null);if(!v.length)return null;
 const first=v[0],last=v[v.length-1];
 return {first,last,change:first>0?last/first-1:null,high:Math.max(...v),low:Math.min(...v)}}
function exItems(){
 const A=exAll(),items=[];
 A.stocks.forEach(x=>{const f=D.firms?.[x.id]||{};items.push({...x,type:'s',group:'Aktien',region:f.region||'',category:f.category||'',stage:f.stage||''})});
 A.etfs.forEach(x=>items.push({...x,type:'e',group:'ETFs'}));
 const rows=D.commodities||[],names=rows.length?Object.keys(rows[0].prices||{}):[];
 names.filter(n=>n!=='energy').forEach(n=>items.push({key:'c:'+n,id:n,type:'c',group:'Rohstoffe',label:typeof cmLabel==='function'?cmLabel(n):n,yearly:true,unit:'% des Basispreises'}));
 if(rows.some(r=>r.electricity))items.push({key:'x:electricity',id:'electricity',type:'x',group:'Strom',label:'Strompreisindex',yearly:true,unit:'% des Basispreises'});
 return items}
function renderStockExplorer(){
 const card=exEnsureCard('sx-explorer',document.getElementById('sx-compare'),'<h3>Alles im Vergleich</h3><p class="hint">Genau einen Eintrag wählen (Aktie, ETF, Rohstoff oder Strompreis), optional mit dem Börsenindex als zweiter Linie. Bei Start = 100 beginnt die Linie mit ihrem ersten Wert im Zeitraum.</p><div class="ex-grid" style="display:grid;grid-template-columns:300px minmax(0,1fr);gap:14px;align-items:start"><div class="ex-side"><div class="filters" style="flex-wrap:wrap"><input id="ex-search" type="search" placeholder="Name suchen …" aria-label="Name suchen" autocomplete="off" style="width:100%"><div class="chips" id="ex-types"></div><select id="ex-f-region" aria-label="Region"></select><select id="ex-f-cat" aria-label="Kategorie"></select><select id="ex-f-stage" aria-label="Stufe"></select><select id="ex-sort" aria-label="Sortierung"><option value="name">Sortierung: Name</option><option value="change">Sortierung: Veränderung</option></select><label style="width:100%;font-size:12px">Aktien: mindestens <input id="ex-minyears" type="number" min="0" max="50" step="1" value="0" style="width:56px" aria-label="Mindestens so viele Jahre an der Börse"> Jahre an der Börse</label></div><div id="ex-list" style="max-height:460px;overflow-y:auto;border:1px solid var(--border,#ccc);border-radius:6px"></div></div><div class="ex-main"><div class="filters"><label>Auflösung <select id="ex-res"><option value="year">Jahr</option><option value="month">Monat</option><option value="week">Woche</option></select></label><label class="switch-line"><input type="checkbox" id="ex-norm"> Start = 100</label><label class="switch-line"><input type="checkbox" id="ex-index"> Börsenindex einblenden</label></div><p class="hint" id="ex-hint" role="status"></p><div class="chart" style="height:460px"><canvas id="ex-chart"></canvas></div><div id="ex-stats" class="hint"></div></div></div><style>@media (max-width:800px){#sx-explorer .ex-grid{grid-template-columns:1fr!important}}#sx-explorer .ex-row{display:flex;justify-content:space-between;gap:8px;width:100%;padding:5px 8px;border:0;background:none;text-align:left;cursor:pointer;color:inherit;font:inherit}#sx-explorer .ex-row:hover{background:rgba(128,128,128,.12)}#sx-explorer .ex-row.active{background:rgba(60,120,220,.22);font-weight:600}#sx-explorer .ex-gh{padding:4px 8px;font-weight:700;font-size:12px;background:rgba(128,128,128,.15);position:sticky;top:0}</style>');
 if(!card)return;
 const old=document.getElementById('sx-compare')?.closest('.card');if(old)old.style.display='none';
 const A=exAll(),items=exItems(),byKey=new Map(items.map(x=>[x.key,x]));
 const top=exTopStocks(A.stocks,1);
 let active=store.get('sx-ex-active',null);
 if(!byKey.has(active))active=top[0]||(items[0]&&items[0].key)||null;
 let res=store.get('sx-ex-res','month');if(!['year','month','week'].includes(res))res='month';
 const norm=!!store.get('sx-ex-norm',true),withIndex=!!store.get('sx-ex-index',true);
 let fl=store.get('sx-ex-filter',null);if(!fl||typeof fl!=='object')fl={};
 fl={q:'',type:'all',region:'',category:'',stage:'',sort:'name',minYears:0,...fl};
 fl.minYears=Math.max(0,Math.min(50,Math.floor(Number(fl.minYears))||0));
 const saveFl=()=>store.set('sx-ex-filter',fl);
 const TYPES=[['all','Alle'],['s','Aktien'],['e','ETFs'],['c','Rohstoffe'],['x','Strom']];
 const uniq=k=>[...new Set(items.filter(x=>x.type==='s'&&x[k]).map(x=>x[k]))];
 const fillSel=(id,label,vals,cur,nameOf)=>{const el=card.querySelector(id);el.innerHTML='<option value="">'+label+': alle</option>'+vals.map(v=>'<option value="'+esc(v)+'"'+(v===cur?' selected':'')+'>'+esc(nameOf(v))+'</option>').join('')};
 fillSel('#ex-f-region','Region',uniq('region').sort(),fl.region,v=>(typeof REGION!=='undefined'&&REGION[v])||v);
 fillSel('#ex-f-cat','Kategorie',uniq('category').sort(),fl.category,v=>({beer:'Bier',wine:'Wein',spirits:'Spirituosen'})[v]||v);
 fillSel('#ex-f-stage','Stufe',uniq('stage').filter(v=>v!=='bank'&&v!=='courier'),fl.stage,v=>(typeof STAGE!=='undefined'&&STAGE[v])||v);
 card.querySelector('#ex-search').value=fl.q;card.querySelector('#ex-sort').value=fl.sort;
 card.querySelector('#ex-res').value=res;card.querySelector('#ex-norm').checked=norm;card.querySelector('#ex-index').checked=withIndex;
 const wPts=stockPoints('week');
 // Liste und Kennzahl unter dem Diagramm nutzen dieselbe Funktion und dieselben Punkte (gewählte Auflösung).
 const pointsOf=x=>exResPoints(x.yearly?'year':res);
 const changes=new Map(items.map(x=>{const s=exStats(exRaw(x,pointsOf(x)));return [x.key,s?s.change:null]}));
 // Jahre an der Börse im gewählten Zeitraum: Jahre mit mindestens einem Kurs > 0.
 const yearsListed=new Map(items.filter(x=>x.type==='s').map(x=>{const ys=new Set();wPts.forEach(i=>{if(D.stocks.prices[x.id]?.[i]>0)ys.add(D.stocks.years[i])});return [x.key,ys.size]}));
 card.querySelector('#ex-minyears').value=fl.minYears;
 const drawList=()=>{
  const q=fl.q.trim().toLowerCase(),stockOnly=!!(fl.region||fl.category||fl.stage);
  let rows=items.filter(x=>(fl.type==='all'||x.type===fl.type)&&(!q||x.label.toLowerCase().includes(q)));
  if(fl.minYears>0)rows=rows.filter(x=>x.type!=='s'||(yearsListed.get(x.key)||0)>=fl.minYears);
  if(stockOnly)rows=rows.filter(x=>x.type==='s'&&(!fl.region||x.region===fl.region)&&(!fl.category||x.category===fl.category)&&(!fl.stage||x.stage===fl.stage));
  const cmp=fl.sort==='change'?(a,b)=>(changes.get(b.key)??-Infinity)-(changes.get(a.key)??-Infinity):(a,b)=>a.label.localeCompare(b.label);
  let html='';
  ['Aktien','ETFs','Rohstoffe','Strom'].forEach(g=>{const r=rows.filter(x=>x.group===g).sort(cmp);if(!r.length)return;
   html+='<div class="ex-gh">'+g+' ('+r.length+')</div>'+r.map(x=>{const c=changes.get(x.key),col=c==null?'':(c>=0?'#1a9850':'#d73027');
    return '<button class="ex-row'+(x.key===active?' active':'')+'" data-key="'+esc(x.key)+'"><span>'+esc(x.label)+'</span><span style="color:'+col+';white-space:nowrap">'+(c==null?'–':(c>=0?'+':'')+nf(c*100,1)+' %')+'</span></button>'}).join('')});
  card.querySelector('#ex-list').innerHTML=html||'<p class="hint" style="padding:8px">Keine Treffer.</p>'};
 const drawTypes=()=>{card.querySelector('#ex-types').innerHTML=TYPES.map(([k,l])=>'<button class="chip" data-type="'+k+'" aria-pressed="'+(fl.type===k)+'">'+l+'</button>').join('');
  const showSt=fl.type==='all'||fl.type==='s';['#ex-f-region','#ex-f-cat','#ex-f-stage'].forEach(s=>card.querySelector(s).style.display=showSt?'':'none')};
 const drawChart=()=>{
  const item=byKey.get(active),hint=card.querySelector('#ex-hint'),statsEl=card.querySelector('#ex-stats');
  if(!item){hint.textContent='Nichts ausgewählt.';statsEl.innerHTML='';chart('ex-chart',{type:'line',data:{labels:[],datasets:[]},options:{}});return}
  const eff=item.yearly?'year':res,points=pointsOf(item);
  const raw=exRaw(item,points),ds=stockDataset(item.label,norm?stockNormal(raw):raw,pal()[0],2.5);
  if(item.yearly)ds.pointRadius=3;
  const datasets=[ds];
  if(withIndex){const ir=exRaw({key:'i:index'},points),di=stockDataset('Börsenindex',norm?stockNormal(ir):ir,pal()[7],2);di.borderColor='rgba(128,128,128,.75)';if(!norm)di.yAxisID='y2';datasets.push(di)}
  hint.textContent=item.yearly?'Für '+item.label+' gibt es nur Jahreswerte, darum wird die Jahres-Achse verwendet.':(raw.some(v=>v!=null)?'Lücken: vor dem Börsengang oder nach dem Austritt gibt es keinen Kurs.':'Keine Kurse im gewählten Zeitraum.');
  const opts=stockOptions(points,eff==='week'?'week':'month');
  opts.scales.y.title={display:true,text:norm?'Start = 100':(item.unit?item.label+' ('+item.unit+')':'Kurs in CHF / ETF-Stand')};
  // Indexstand ist eine Zahl, kein Prozentwert (auch auf der rechten Achse bei Start = 100 aus).
  opts.plugins.tooltip.callbacks.label=c=>c.dataset.label+': '+(c.parsed.y==null?'–':nf(c.parsed.y,2));
  opts.plugins.tooltip.mode='index';opts.plugins.tooltip.intersect=false;opts.interaction={mode:'index',intersect:false};
  if(eff==='year')opts.plugins.tooltip.callbacks.title=its=>its.length?'Jahr '+D.stocks.years[points[its[0].dataIndex]]:'';
  if(!norm&&withIndex)opts.scales.y2={position:'right',grid:{display:false},title:{display:true,text:'Indexstand'},...fmtAxis()};
  opts.plugins.legend={display:true,labels:{boxWidth:10,font:{size:11}}};
  chart('ex-chart',{type:'line',data:{labels:points.map(i=>eff==='year'?'Jahr '+D.stocks.years[i]:stockLabel(i,eff)),datasets},options:opts});
  const s=exStats(raw),u=item.type==='s'?' CHF':item.type==='e'?'':' %';
  statsEl.innerHTML=s?'<b>'+esc(item.label)+'</b>: Letzter Wert '+nf(s.last,2)+u+' · Veränderung '+(s.change==null?'–':(s.change>=0?'+':'')+nf(s.change*100,1)+' %')+' · Hoch '+nf(s.high,2)+u+' · Tief '+nf(s.low,2)+u:'<b>'+esc(item.label)+'</b>: keine Werte im gewählten Zeitraum.'};
 store.set('sx-ex-active',active);
 card.querySelector('#ex-types').onclick=e=>{const b=e.target.closest('button[data-type]');if(!b)return;fl.type=b.dataset.type;saveFl();drawTypes();drawList()};
 card.querySelector('#ex-search').oninput=e=>{fl.q=e.target.value;saveFl();drawList()};
 card.querySelector('#ex-f-region').onchange=e=>{fl.region=e.target.value;saveFl();drawList()};
 card.querySelector('#ex-f-cat').onchange=e=>{fl.category=e.target.value;saveFl();drawList()};
 card.querySelector('#ex-f-stage').onchange=e=>{fl.stage=e.target.value;saveFl();drawList()};
 card.querySelector('#ex-minyears').oninput=e=>{fl.minYears=Math.max(0,Math.min(50,Math.floor(Number(e.target.value))||0));saveFl();drawList()};
 card.querySelector('#ex-sort').onchange=e=>{fl.sort=e.target.value;saveFl();drawList()};
 card.querySelector('#ex-list').onclick=e=>{const b=e.target.closest('button[data-key]');if(!b)return;active=b.dataset.key;store.set('sx-ex-active',active);drawList();drawChart()};
 card.querySelector('#ex-res').onchange=e=>{store.set('sx-ex-res',e.target.value);renderStockExplorer()};
 card.querySelector('#ex-norm').onchange=e=>{store.set('sx-ex-norm',e.target.checked);renderStockExplorer()};
 card.querySelector('#ex-index').onchange=e=>{store.set('sx-ex-index',e.target.checked);renderStockExplorer()};
 drawTypes();drawList();drawChart()}
