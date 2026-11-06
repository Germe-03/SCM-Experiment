Object.assign(EVENT,{holding_formed:'Holding gegründet',holding_acquisition:'Tochter gekauft',holding_sweep:'Reserve abgeschöpft',holding_cover:'Holding deckt Verluste',holding_no_cover:'Holding stützt nicht',holding_sold:'Tochter verkauft',holding_takeover:'Holding gekauft',holding_dissolved:'Holding aufgelöst',holding_daughter_lost:'Tochter ausgeschieden',merger:'Fusion',merger_blocked:'Fusion verboten'});

function holdingGroupsList(){return (D.holding_groups||[]).filter(g=>g.founded_year<=range.to&&(!g.dissolved_year||g.dissolved_year>=range.from))}
function holdingSuccessorName(id){
 if(!id)return '';
 if(typeof firm==='function'&&firm(id))return fname(id);
 const group=(D.holding_groups||[]).find(g=>String(g.holding)===String(id));
 return group?.name||fname(id)
}
function holdingTable(groups,mode){
 if(!groups.length)return empty('In diesem Lauf ist keine Holding entstanden.');
 return groups.map(g=>{
  const status=g.status==='active'?'aktiv seit Jahr '+esc(g.founded_year):'aufgelöst in Jahr '+esc(g.dissolved_year)+(g.successor?', Nachfolger: '+esc(holdingSuccessorName(g.successor)):'');
  const subs=g.subs||[],logs=(D.holding_log||[]).filter(log=>String(log.holding)===String(g.holding)&&inRange(log.year)).slice(-6);
  let html='<section class="holding-block"><h4>'+esc(g.name)+'</h4><p>'+status+'</p><p>Kasse der Holding: '+chf(g.cash??0)+'</p>';
  if(mode==='stocks'){
   html+='<p>Börsenkürzel: '+esc(fname(g.listing_id))+' (Kurs wird als Holding fortgeführt)</p>';
   if(hasStockPrices(g.listing_id))html+='<button class="btn" data-hg-stock="'+esc(g.listing_id)+'">Kurs vergleichen</button>'
  }
  if(mode==='compare')html+='<button class="btn" data-hg-cmp="'+esc(g.holding)+'">Holding und Töchter vergleichen</button>';
  html+='<div class="table-wrap"><table><thead><tr><th>Tochter</th><th>Status</th><th>Umsatz</th><th>Gewinn</th><th>Kasse</th><th>Reserve</th></tr></thead><tbody>'+subs.map(s=>'<tr class="click" data-firm="'+esc(s.firm)+'"><td>'+esc(s.name)+'</td><td>'+(s.active?'aktiv':'ausgeschieden')+'</td><td class="num">'+chf(s.revenue??0)+'</td><td class="num">'+chf(s.profit??0)+'</td><td class="num">'+chf(s.cash??0)+'</td><td class="num" title="Mindestreserve: '+esc(chf(s.reserve_floor??0))+'">'+chf(s.reserve??0)+'</td></tr>').join('')+'</tbody></table></div><ul class="list">'+logs.map(log=>'<li>Jahr '+esc(log.year)+': '+esc(log.details||'')+'</li>').join('')+'</ul></section>';
  return html
 }).join('')
}
function renderHoldingGroups(boxId,mode){
 const box=$('#'+boxId);
 if(!box)return;
 box.innerHTML='<div class="card wide"><h3>Holdings und Töchter</h3>'+holdingTable(holdingGroupsList(),mode)+'</div>';
 wireFirmLinks(box);
 box.querySelectorAll('button[data-hg-stock]').forEach(button=>{button.onclick=()=>addStock(button.dataset.hgStock)});
 box.querySelectorAll('button[data-hg-cmp]').forEach(button=>{button.onclick=()=>{
  const group=(D.holding_groups||[]).find(g=>String(g.holding)===String(button.dataset.hgCmp));
  if(!group)return;
  S.cmp=[...new Set([group.listing_id,...(group.subs||[]).map(s=>s.firm)])].filter(id=>typeof firm==='function'&&firm(id)).slice(0,6);
  store.set('cmp',S.cmp);
  renderCompare()
 }})
}
function wrapHoldingView(tab,mode,box){
 const old=VIEWS[tab];
 VIEWS[tab]=()=>{if(typeof old==='function')old();renderHoldingGroups(box,mode)}
}
if(typeof VIEWS!=='undefined')[['firms','firms','hg-firms'],['compare','compare','hg-compare'],['stocks','stocks','hg-stocks']].forEach(args=>wrapHoldingView(...args));
