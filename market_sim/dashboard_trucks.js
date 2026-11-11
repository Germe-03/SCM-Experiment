// Phase 53: Lastwagen, Occasionen und Händler im Reiter Kuriere.
Object.assign(EVENT,{truck_bought:'Lastwagen gekauft',truck_sold_used:'Occasion verkauft',truck_repaired:'Lastwagen repariert',truck_scrapped:'Totalschaden / Entsorgung',truck_dealer_entry:'Neuer Lastwagenhändler',truck_dealer_exit:'Lastwagenhändler gibt auf',policy_rate_emergency:'Leitzins: ausserordentlicher Eingriff',rnd_inherited:'Forschungsstand übernommen',strategy_change:'Neu eingestuft'});
function renderTrucks(){
 const box=document.getElementById('trucks-box');if(!box)return;
 const T=D.trucks||{};
 if(!T.enabled){box.innerHTML='';return}
 const types=T.types||[],label=Object.fromEntries(types.map(t=>[t.name,t.label]));
 const years=[...new Set([...(T.fleet||[]).filter(r=>r.kind!=='carrier'),...(T.dealers||[]),...(T.prices||[])].map(r=>r.year))].sort((a,b)=>a-b);
 const sumBy=(rows,y,key,f)=>rows.filter(r=>r.year===y&&(!f||f(r))).reduce((a,r)=>a+(+r[key]||0),0);
 const last=years.at(-1),fleet=(T.fleet||[]).filter(r=>r.kind!=='carrier'),dealers=T.dealers||[],workshop=T.workshop||[];
 const firmsWith=new Set(fleet.filter(r=>r.year===last).map(r=>r.firm)).size;
 const price=(T.prices||[]).find(r=>r.year===last);
 const allHolds=Array.isArray(D.holdings)?D.holdings.filter(h=>h&&h.action==null):[];
 const holdYear=Math.max(...allHolds.map(h=>h.year),0),holds=allHolds.filter(h=>h.year===holdYear);
 const dealerRows=dealers.filter(r=>r.year===last);
 const dealerId=r=>r.id??r.dealer_id??r.dealer??r.firm;
 const stakesOf=r=>holds.filter(h=>h.owner===dealerId(r)).map(h=>(typeof fname==='function'?fname(h.target):h.target)+(h.share!=null?' ('+pct(h.share)+')':''));
 const dealerDetail=dealerRows.map(r=>({...r,revenue_new:+r.revenue_new||0,revenue_used:+r.revenue_used||0,revenue_workshop:+r.revenue_workshop||0,workshop_jobs:+r.workshop_jobs||0,service_contracts:+r.service_contracts||0,stakes:[...new Set(stakesOf(r))]}));
 const dealerWorkshop=d=>workshop.filter(w=>w.year===last&&w.dealer===dealerId(d)).length;
 box.innerHTML=`<h3>Lastwagen</h3><div class="kpis">${[
  kpi('Lastwagen im Besitz von Firmen',nf(sumBy(fleet,last,'count'))),
  kpi('Firmen mit eigener Flotte',nf(firmsWith)),
  kpi('Käufe total',nf((T.purchases||[]).length),'davon Occasion: '+nf((T.purchases||[]).filter(p=>p.used).length)),
  kpi('Occasionen zurückverkauft',nf((T.occasions||[]).length)),
  kpi('Totalschäden / Entsorgungen',nf((T.disposals||[]).length),'Kosten '+chf((T.disposals||[]).reduce((a,d)=>a+d.cost,0))),
  kpi('Preis mittlerer Lastwagen',chf(price?.prices?.mittel))].join('')}</div>
 <div class="grid"><div class="card"><h3>Flotte nach Typ</h3><div class="chart"><canvas id="tr-fleet"></canvas></div></div>
 <div class="card"><h3>Käufe, Occasionen und Entsorgungen pro Jahr</h3><div class="chart"><canvas id="tr-flow"></canvas></div></div>
 <div class="card"><h3>Lastwagenpreis (Marktpreis)</h3><div class="chart"><canvas id="tr-price"></canvas></div></div></div>
 <div class="card"><h3>Lastwagenhändler</h3><table><thead><tr><th>Händler</th><th>Jahr</th><th>Lager neu</th><th>Lager Occasion</th><th>Verkauft neu</th><th>Occasion zurückgenommen</th><th>Limite</th><th>Umsatz</th><th>Gewinn</th><th>Kasse</th></tr></thead><tbody>${
  dealers.filter(r=>r.year===last).map(r=>`<tr><td>${esc(r.name)}</td><td class="num">${r.year}</td><td class="num">${nf(r.stock_new)}</td><td class="num">${nf(r.stock_used)}</td><td class="num">${nf(r.sold_new)}</td><td class="num">${nf(r.taken_back)}</td><td class="num">${nf(r.takeback_limit)}</td><td class="num">${chf(r.revenue)}</td><td class="num">${chf(r.profit)}</td><td class="num">${chf(r.cash)}</td></tr>`).join('')||'<tr><td colspan="10">Keine Händler aktiv</td></tr>'}</tbody></table></div>
 <div class="card"><h3>Händler im Detail: Umsatz, Werkstatt, Serviceverträge, Beteiligungen</h3><p class="hint">Letztes Jahr im gewählten Zeitraum. Umsatz gestapelt nach Neu, Occasion und Werkstatt (CHF).</p><div class="grid"><div class="chart"><canvas id="tr-dealer-rev"></canvas></div><div class="chart"><canvas id="tr-dealer-jobs"></canvas></div></div>
 <table><thead><tr><th>Händler</th><th>Umsatz Neu</th><th>Umsatz Occasion</th><th>Umsatz Werkstatt</th><th>Werkstatt-Aufträge</th><th>Laufende Serviceverträge</th><th>Beteiligungen</th></tr></thead><tbody>${
  dealerDetail.map(r=>`<tr><td>${esc(r.name)}</td><td class="num">${chf(r.revenue_new)}</td><td class="num">${chf(r.revenue_used)}</td><td class="num">${chf(r.revenue_workshop)}</td><td class="num">${nf(r.workshop_jobs)}</td><td class="num">${nf(r.service_contracts)}</td><td>${r.stakes.length?r.stakes.map(esc).join(', '):'–'}</td></tr>`).join('')||'<tr><td colspan="7">Keine Händlerdaten</td></tr>'}</tbody></table></div>`;
 const count=(rows,y)=>rows.filter(r=>r.year===y).length;
 if(dealerDetail.length&&$('#tr-dealer-rev')){
  const dl=dealerDetail.map(r=>r.name);
  chart('tr-dealer-rev',{type:'bar',data:{labels:dl,datasets:[['Neu','revenue_new'],['Occasion','revenue_used'],['Werkstatt','revenue_workshop']].map(([l,k],i)=>({label:l,data:dealerDetail.map(r=>r[k]),backgroundColor:pal()[i]+'cc'}))},options:{scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,ticks:{callback:v=>chf(v)}}}}});
  chart('tr-dealer-jobs',{type:'bar',data:{labels:dl,datasets:[{label:'Werkstatt-Aufträge',data:dealerDetail.map(r=>r.workshop_jobs||dealerWorkshop(r)),backgroundColor:pal()[3]+'cc'},{label:'Laufende Serviceverträge',data:dealerDetail.map(r=>r.service_contracts),backgroundColor:pal()[4]+'cc'}]},options:{scales:{x:{grid:{display:false}}}}})
 }
 chart('tr-fleet',{type:'bar',data:{labels:years,datasets:types.map((t,i)=>({label:t.label,data:years.map(y=>sumBy(fleet,y,'count',r=>r.type===t.name)),backgroundColor:pal()[i%8]+'cc'}))},options:{scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true}}}});
 chart('tr-flow',{type:'bar',data:{labels:years,datasets:[
  {label:'Käufe',data:years.map(y=>count(T.purchases||[],y)),backgroundColor:pal()[0]+'cc'},
  {label:'Occasion verkauft',data:years.map(y=>count(T.occasions||[],y)),backgroundColor:pal()[2]+'cc'},
  {label:'Entsorgt (Totalschaden/Lebensende)',data:years.map(y=>count(T.disposals||[],y)),backgroundColor:css('--bad')+'bb'}]},options:{scales:{x:{grid:{display:false}}}}});
 chart('tr-price',{type:'line',data:{labels:years,datasets:types.map((t,i)=>({label:t.label,data:years.map(y=>(T.prices||[]).find(r=>r.year===y)?.prices?.[t.name]??null),borderColor:pal()[i%8],pointRadius:0,borderWidth:2,tension:.2}))},options:{scales:{y:{ticks:{callback:v=>chf(v)}}}}});
}
if(typeof VIEWS!=='undefined')VIEWS.couriers=()=>{renderCouriers();renderTrucks()};

