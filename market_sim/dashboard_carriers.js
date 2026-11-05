// Phase 30: Post und Kuriere im Reiter Transport.
function carrierYears(){
 return [...new Set((D.carriers||[]).map(row=>row.year))].sort((a,b)=>a-b)
}
function postRows(){
 return (D.carriers||[]).filter(row=>row.carrier==='post').sort((a,b)=>a.year-b.year)
}
function couriersByRegion(year){
 const counts={};
 for(const row of (D.carriers||[]).filter(row=>row.year===year&&row.kind==='courier')){
  for(const region of String(row.regions||'').split(';').filter(Boolean))counts[region]=(counts[region]||0)+1
 }
 return counts
}
function renderTransport(){
 const rows=D.carriers||[];
 if(!rows.length){
  $('#tr-kpis').innerHTML=empty('Post und Kuriere sind in diesem Lauf ausgeschaltet (carriers.enabled).');
  $('#tr-table').innerHTML='';
  $('#tr-map').innerHTML='';
  return
 }

 const years=carrierYears(),lastYear=years.at(-1),post=postRows(),lastPost=post.find(row=>row.year===lastYear);
 const sum=(list,key)=>list.reduce((total,row)=>total+(+row[key]||0),0);
 $('#tr-kpis').innerHTML=[
  kpi('Posttarif letztes Jahr',nf(lastPost?.next_tariff,3)+' CHF'),
  kpi('Bundesbeitrag total',chf(sum(rows,'bundesbeitrag'))),
  kpi('Anteil eigene Flotte',pct(lastPost?.share_own)),
  kpi('Anteil Post',pct(lastPost?.share_post)),
  kpi('Anteil Kuriere',pct(lastPost?.share_couriers)),
  kpi('Aktive Kuriere im letzten Jahr',nf(rows.filter(row=>row.year===lastYear&&row.kind==='courier').length))
 ].join('');

 const postByYear=Object.fromEntries(post.map(row=>[row.year,row]));
 const yearsWithRows=years.map(year=>postByYear[year]||null);
 const shares=[
  ['Eigene Flotte','share_own'],
  ['Post','share_post'],
  ['Kuriere','share_couriers']
 ];
 chart('tr-shares',{type:'line',data:{labels:years,datasets:shares.map(([label,key],i)=>({
  label,data:yearsWithRows.map(row=>row&&row[key]!=null?row[key]*100:null),
  borderColor:pal()[i],backgroundColor:pal()[i]+'55',fill:'stack',pointRadius:0,borderWidth:2
 }))},options:{scales:{
  x:{grid:{display:false}},
  y:{stacked:true,min:0,max:100,ticks:{callback:value=>pct(value/100)}}
 }}});

 chart('tr-post',{type:'bar',data:{labels:years,datasets:[
  {label:'Bundesbeitrag (Mio. CHF)',data:yearsWithRows.map(row=>row?row.bundesbeitrag/1e6:null),backgroundColor:pal()[0]+'aa',yAxisID:'y',order:2},
  {type:'line',label:'Posttarif (CHF pro Einheit und km)',data:yearsWithRows.map(row=>row?.tariff??null),borderColor:pal()[1],pointRadius:0,borderWidth:2,yAxisID:'y1',order:1}
 ]},options:{scales:{
  x:{grid:{display:false}},
  y:{title:{display:true,text:'Mio. CHF'},ticks:{callback:value=>nf(value,1)}},
  y1:{position:'right',grid:{display:false},title:{display:true,text:'CHF pro Einheit und km'},ticks:{callback:value=>nf(value,3)}}
 }}});

 const courierDelay=year=>{
  const couriers=rows.filter(row=>row.year===year&&row.kind==='courier');
  const units=sum(couriers,'units');
  return units?couriers.reduce((total,row)=>total+(+row.mean_delay_days||0)*(+row.units||0),0)/units:null
 };
 chart('tr-delay',{type:'line',data:{labels:years,datasets:[
  {label:'Post',data:yearsWithRows.map(row=>row?.mean_delay_days??null),borderColor:pal()[0],pointRadius:0,borderWidth:2},
  {label:'Kuriere',data:years.map(courierDelay),borderColor:pal()[1],pointRadius:0,borderWidth:2}
 ]},options:{scales:{x:{grid:{display:false}},y:{beginAtZero:true,ticks:{callback:value=>nf(value,1)}}}}});

 const regions=D.regions||[],counts=couriersByRegion(lastYear);
 const map=$('#tr-map');
 map.innerHTML=regions.map(region=>{
  const count=counts[region.name]||0,name=REGION[region.name]||region.name;
  const x=20+(Number(region.x)-470)/300*360,y=240-(Number(region.y)-60)/250*220,radius=8+6*count;
  const label=count===0?'keine Kuriere':count===1?'1 Kurier':count+' Kuriere';
  return `<g><circle cx="${x}" cy="${y}" r="${radius}" fill="${count>0?pal()[1]:'#bbb'}"><title>${esc(name)}</title></circle><text x="${x}" y="${y+radius+13}" text-anchor="middle" font-size="10">${esc(name)}: ${label}</text></g>`
 }).join('');

 const byCarrier=new Map();
 for(const row of rows){
  if(!byCarrier.has(row.carrier))byCarrier.set(row.carrier,[]);
  byCarrier.get(row.carrier).push(row)
 }
 const carriers=[...byCarrier.entries()].sort((a,b)=>{
  if(a[0]==='post')return -1;
  if(b[0]==='post')return 1;
  return String(a[1][0].name||a[0]).localeCompare(String(b[1][0].name||b[0]),'de-CH')
 });
 const headers=['Name','Art','Jahre','Regionen zuletzt','Einheiten total','Umsatz total','Gewinn total','Bundesbeitrag total','Verspätung (mittlere Tage)','Status'];
 const body=carriers.map(([id,history])=>{
  history.sort((a,b)=>a.year-b.year);
  const first=history[0],latest=history.at(-1),carrierYearsSeen=history.map(row=>row.year);
  const units=sum(history,'units'),weightedDelay=units?history.reduce((total,row)=>total+(+row.mean_delay_days||0)*(+row.units||0),0)/units:null;
  const regions=String(latest.regions||'').split(';').filter(Boolean).map(region=>REGION[region]||region).join(', ')||'–';
  const active=history.some(row=>row.year===lastYear);
  const kind=first.kind==='post'?'Post':'Kurier';
  const numeric=(value,text)=>`<td class="num" data-value="${value==null?'':value}">${text}</td>`;
  return `<tr><td>${esc(first.name||id)}</td><td>${kind}</td><td>${first.year}–${latest.year}</td><td>${esc(regions)}</td>${numeric(units,nf(units))}${numeric(sum(history,'revenue'),chf(sum(history,'revenue')))}${numeric(sum(history,'profit'),chf(sum(history,'profit')))}${numeric(sum(history,'bundesbeitrag'),chf(sum(history,'bundesbeitrag')))}${numeric(weightedDelay,nf(weightedDelay,2))}<td>${active?'aktiv':'ausgeschieden'}</td></tr>`
 }).join('');
 $('#tr-table').innerHTML=`<thead><tr>${headers.map((header,index)=>`<th${index>=4&&index<=8?' class="num"':''}>${header}</th>`).join('')}</tr></thead><tbody>${body}</tbody>`
}
