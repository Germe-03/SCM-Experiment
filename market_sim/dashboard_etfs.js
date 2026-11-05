// Phase 23: ETFs im Reiter Börse (nur Anzeige, noch nicht kaufbar).
function etfName(def){if(def.kind==='region')return 'ETF '+(REGION[def.key]||def.key);if(def.kind==='category')return 'ETF '+({beer:'Bier',wine:'Wein',spirits:'Spirituosen'}[def.key]||def.key);return 'ETF '+fmGroupLabel(def.key)}
function etfWeights(def,i){
 const members=def.members.filter(id=>{const price=D.stocks?.prices?.[id]?.[i];return price!=null&&price>0});
 if(!members.length)return [];
 const total=members.reduce((sum,id)=>sum+D.stocks.prices[id][i],0);
 return members.map(id=>({id,weight:D.etfs.weighting==='market_cap'?D.stocks.prices[id][i]/total:1/members.length})).sort((a,b)=>b.weight-a.weight)
}
function etfsOf(firmId){return D.etfs?D.etfs.definitions.filter(def=>def.members.includes(firmId)):[]}
function etfMembership(firmId){const defs=etfsOf(firmId);return defs.length?'<p class="hint">Enthalten in: '+defs.map(def=>esc(etfName(def))).join(', ')+'</p>':''}
function etfRow(def,points){
 const levels=D.etfs.levels[def.id]||[];
 let first=null,last=null;
 points.forEach(i=>{const value=levels[i];if(value==null)return;if(first===null)first=i;last=i});
 const firms=first===null?0:def.members.filter(id=>(D.stocks.prices[id]?.[last]||0)>0).length,level=first===null?null:levels[last];
 const change=level!=null&&levels[first]>0?level/levels[first]-1:null,top=first===null?null:etfWeights(def,last)[0];
 return '<tr class="click" tabindex="0" data-etf="'+esc(def.id)+'"><td>'+esc(etfName(def))+'</td><td class="num" data-value="'+firms+'">'+nf(firms,0)+'</td><td class="num" data-value="'+(level==null?'':level)+'">'+(level==null?'–':nf(level,2))+'</td><td class="num" data-value="'+(change==null?'':change*100)+'">'+(change==null?'–':pct(change))+'</td><td>'+(top?actorLabel(top.id)+' ('+pct(top.weight)+')':'–')+'</td></tr>'
}
function renderEtfs(){
 const chips=[['region','Regionen'],['category','Kategorien'],['stage','Stufen']];
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
 target.innerHTML='<h3>Mitglieder: '+esc(etfName(def))+'</h3>'+(last===null?empty('Im Zeitraum ohne Kurs.'):'<div class="table-wrap"><table id="etf-member-table"><thead><tr><th>Firma</th><th>Gewicht</th><th>Kurs</th></tr></thead><tbody>'+etfWeights(def,last).map(entry=>{const price=D.stocks.prices[entry.id][last];return '<tr><td><a href="#firms" data-firm="'+esc(entry.id)+'">'+actorLabel(entry.id)+'</a></td><td class="num" data-value="'+entry.weight*100+'">'+pct(entry.weight)+'</td><td class="num" data-value="'+price+'">'+nf(price,2)+' CHF</td></tr>'}).join('')+'</tbody></table></div>');
 wireFirmLinks(target)
}
