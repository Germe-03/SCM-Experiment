// Phase 27: Forschungsbäume, Patente, Schadenersatz (Reiter F&E, Firmendetails, Finanzen, Staat).
function rndTreeNames(){return {factory:'Hersteller',distributor:'Verteilung',wholesaler:'Grosshandel',retailer:'Detailhandel',restaurant:'Gastronomie'}}
function rndLabel(tree,name){const stages=D.rnd_trees&&D.rnd_trees[tree]||[],stage=stages.find(x=>x.name===name);return stage?stage.label||stage.name:name}
function rndStep(row){return row.step==='implementation'?'Umsetzung':'Forschung'}
function rndRowTree(row){
 if(row.tree)return row.tree;
 const trees=D.rnd_trees||{};
 for(const tree in trees)if((trees[tree]||[]).some(stage=>stage.name===row.project))return tree;
 return null
}
function rndProgress(tree,firmId=null){
 const stages=D.rnd_trees&&D.rnd_trees[tree]||[],out={};
 stages.forEach(stage=>{out[stage.name]={researched:0,implemented:0,firms:{}}});
 (D.rnd||[]).forEach(row=>{
  if(rndRowTree(row)!==tree||row.end_year>range.to||(firmId&&row.firm!==firmId)||!row.success)return;
  const entry=out[row.project];if(!entry)return;
  if(rndStep(row)==='Umsetzung')entry.firms[row.firm]='implemented';
  else if(entry.firms[row.firm]!=='implemented')entry.firms[row.firm]='researched'
 });
 Object.keys(out).forEach(name=>Object.keys(out[name].firms).forEach(id=>{
  if(out[name].firms[id]==='implemented')out[name].implemented++;
  else if(out[name].firms[id]==='researched')out[name].researched++
 }));
 return out
}
function rndPatent(tree,stage,year){
 let latest=null;
 (D.patents||[]).forEach(row=>{if(row.tree===tree&&row.stage===stage&&row.granted_year<=year&&(!latest||row.granted_year>latest.granted_year))latest=row});
 return latest?Object.assign({},latest,{active:latest.end_year==null||year<latest.end_year}):null
}
function rndTreeSvg(tree,firmId=null){
 const stages=D.rnd_trees&&D.rnd_trees[tree];if(!stages)return '';
 const byName={},depths={},visiting={};
 stages.forEach(stage=>{byName[stage.name]=stage});
 function depth(name){
  if(depths[name]!=null)return depths[name];
  if(visiting[name])return 0;
  visiting[name]=true;
  const stage=byName[name],req=(stage.requires||[]).filter(x=>byName[x]);
  let value=0;req.forEach(x=>{value=Math.max(value,depth(x)+1)});
  delete visiting[name];depths[name]=value;return value
 }
 stages.forEach(stage=>depth(stage.name));
 const columns={};stages.forEach(stage=>{const d=depths[stage.name];if(!columns[d])columns[d]=[];columns[d].push(stage.name)});
 const positions={};let maxDepth=0,maxRows=1;
 Object.keys(columns).forEach(key=>{const d=Number(key);maxDepth=Math.max(maxDepth,d);maxRows=Math.max(maxRows,columns[key].length);columns[key].forEach((name,i)=>{positions[name]={x:20+d*290,y:20+i*92}})});
 const width=40+maxDepth*290+250,height=24+maxRows*92,progress=rndProgress(tree,firmId),suffix=String(tree)+'-'+String(firmId||'sector'),marker='rnd-arrow-'+suffix.replace(/[^a-zA-Z0-9_-]/g,'_');
 let svg='<svg width="100%" viewBox="0 0 '+width+' '+height+'" role="img" aria-label="'+esc(rndTreeNames()[tree]||tree)+'">';
 svg+='<defs><marker id="'+esc(marker)+'" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--muted)"/></marker></defs>';
 stages.forEach(stage=>(stage.requires||[]).filter(name=>byName[name]).forEach(name=>{
  const from=positions[name],to=positions[stage.name],x1=from.x+250,y1=from.y+38,x2=to.x,y2=to.y+38,mid=(x1+x2)/2,edge=esc(name).replace(/&gt;/g,'>')+'>'+esc(stage.name).replace(/&gt;/g,'>');
  svg+='<path data-edge="'+edge+'" d="M'+x1+' '+y1+' C'+mid+' '+y1+' '+mid+' '+y2+' '+x2+' '+y2+'" fill="none" stroke="var(--muted)" marker-end="url(#'+esc(marker)+')"/>'
 }));
 stages.forEach(stage=>{
  const name=stage.name,pos=positions[name],info=progress[name],state=firmId?(info.firms[firmId]||'open'):(info.implemented?'implemented':info.researched?'researched':'open');
  const patent=rndPatent(tree,name,range.to),active=patent&&patent.active;
  let style=state==='implemented'?'fill:var(--good);fill-opacity:.18;stroke:var(--good)':state==='researched'?'fill:var(--c4);fill-opacity:.18;stroke:var(--c4)':'fill:var(--soft);stroke:var(--line)';
  style+=';stroke-width:'+(active?'3':'1');
  if(active)style=style.replace(/stroke:var\(--(?:good|c4|line)\)/,'stroke:var(--accent)');
  const label=rndLabel(tree,name),lines=[];
  if(firmId)lines.push(state==='implemented'?'umgesetzt':state==='researched'?'erforscht':'offen');
  else lines.push('erforscht '+info.researched+' · umgesetzt '+info.implemented);
  if(patent){
   if(active){
    let patentLine='Patent: '+esc(fname(patent.holder))+' bis Jahr '+esc(patent.expires_year);
    if((!firmId||patent.holder!==firmId)&&!(patent.prior_users||[]).includes(firmId)){lines.push(patentLine);patentLine=firmId?'gesperrt':'gesperrt für andere'}
    lines.push(patentLine)
   }else lines.push('Patent abgelaufen (Jahr '+esc(patent.end_year)+')')
  }else if(stage.patentable)lines.push('patentierbar');
  svg+='<g data-stage="'+esc(name)+'" data-state="'+state+'"><title>'+esc(label)+'</title><rect x="'+pos.x+'" y="'+pos.y+'" width="250" height="76" rx="9" style="'+style+'"/><text x="'+(pos.x+10)+'" y="'+(pos.y+19)+'" fill="var(--ink)" font-size="12">'+esc(label)+'</text>';
  lines.forEach((line,i)=>{svg+='<text x="'+(pos.x+10)+'" y="'+(pos.y+36+i*14)+'" fill="var(--muted)" font-size="11">'+line+'</text>'});
  svg+='</g>'
 });
 return svg+'</svg>'
}
function renderRndTrees(){
 const names=rndTreeNames(),trees=Object.keys(names).filter(tree=>D.rnd_trees&&D.rnd_trees[tree]);
 if(!trees.length){$('#rd-tree-chips').innerHTML='';$('#rd-tree').innerHTML=empty('In diesem Lauf gibt es keine Forschungsbäume.');return}
 let tree=S.rdTree||store.get('rd-tree','factory');if(!trees.includes(tree))tree=trees[0];S.rdTree=tree;
 $('#rd-tree-chips').innerHTML=trees.map(key=>'<button class="chip" data-tree="'+esc(key)+'" aria-pressed="'+(key===tree?'true':'false')+'">'+esc(names[key])+'</button>').join('');
 $('#rd-tree-chips').onclick=e=>{const b=e.target.closest('button[data-tree]');if(!b)return;S.rdTree=b.dataset.tree;store.set('rd-tree',S.rdTree);renderRndTrees()};
 $('#rd-tree').innerHTML='<p class="hint"><span style="color:var(--good)">■</span> umgesetzt · <span style="color:var(--c4)">■</span> erforscht · <span style="color:var(--muted)">■</span> offen · <span style="color:var(--accent)">■</span> Patent aktiv · Stand Ende Jahr '+range.to+'</p>'+rndTreeSvg(tree)
}
function renderPatentTable(){
 const rows=(D.patents||[]).filter(row=>row.granted_year<=range.to).slice().sort((a,b)=>b.granted_year-a.granted_year);
 let body=rows.length?rows.map(row=>{
  const ended=row.end_year!=null&&row.end_year<=range.to,status=ended?(row.status==='lapsed'?'verfallen':'abgelaufen'):'aktiv';
  return '<tr class="click" data-firm="'+esc(row.holder)+'"><td>'+esc(rndLabel(row.tree,row.stage))+'<br><span class="hint">'+esc(rndTreeNames()[row.tree]||row.tree)+'</span></td><td>'+actorLabel(row.holder)+'</td><td class="num" data-value="'+row.granted_year+'">Jahr '+row.granted_year+'</td><td class="num" data-value="'+esc(row.expires_year)+'">'+esc(row.expires_year)+'</td><td class="num" data-value="'+esc(row.years)+'">'+esc(row.years)+' Jahre</td><td class="num" data-value="'+esc(row.fee)+'">'+chf(row.fee)+'</td><td><span class="badge'+(ended?'':' ok')+'">'+status+'</span></td></tr>'
 }).join(''):'<tr><td colspan="7">'+empty('Bis Jahr '+range.to+' wurde kein Patent erteilt.')+'</td></tr>';
 $('#rd-patents').innerHTML='<thead><tr><th>Stufe</th><th>Inhaber</th><th class="num">erteilt</th><th class="num">Ablauf</th><th class="num">Laufzeit</th><th class="num">Gebühr</th><th>Status</th></tr></thead><tbody>'+body+'</tbody>';
 wireFirmLinks($('#rd-patents'))
}
function firmDamages(id){
 let paid=0,received=0;
 (firm(id)&&firm(id).yearly||[]).forEach(row=>{if(!inRange(row.year))return;Object.keys(row.cash_flows||{}).forEach(key=>{if(key.indexOf('schadenersatz:')!==0)return;const amount=row.cash_flows[key];if(amount<0)paid-=amount;else received+=amount})});
 return {paid:paid,received:received}
}
function firmTree(f){return f.channel==='restaurant'?'restaurant':f.stage}
function firmRndHtml(id){
 const f=firm(id);if(!f)return '';
 const damages=firmDamages(id),patents=(D.patents||[]).filter(row=>(row.holder===id||row.first_holder===id)&&row.granted_year<=range.to);
 const patentHtml=patents.length?'<p class="hint">Patente: '+patents.map(row=>{
  const status=row.end_year!=null&&row.end_year<=range.to?(row.status==='lapsed'?'verfallen':'abgelaufen'):'aktiv';
  return esc(rndLabel(row.tree,row.stage))+' (Jahr '+esc(row.granted_year)+' bis '+esc(row.expires_year)+', '+status+')'
 }).join(', ')+'</p>':'<p class="hint">Keine eigenen Patente.</p>';
 return '<div class="card wide"><h3>Forschung und Patente</h3><div class="kpis">'+kpi('Schadenersatz bezahlt',chf(damages.paid)) +kpi('Schadenersatz erhalten',chf(damages.received))+'</div>'+patentHtml+rndTreeSvg(firmTree(f),id)+'</div>'
}
function rndSplit(rows,year,total){
 let research=0,implementation=0;
 (rows||[]).forEach(row=>{
  const start=row.start_year,end=row.end_year,first=end<start?end:start,last=end,count=last-first+1;
  if(year<first||year>last||count<=0)return;
  const share=row.cost/count;
  if(rndStep(row)==='Umsetzung')implementation+=share;else research+=share
 });
 const sum=research+implementation;
 if(sum>0){research=research*total/sum;implementation=implementation*total/sum}
 else{research=total;implementation=0}
 return {research:research,implementation:implementation}
}
function renderRndMoney(canvasId){
 const s=sys(),firms=D.firms||{},allFirms=Object.keys(firms).map(id=>firms[id]);
 const research=[],implementation=[],fees=[],damages=[];
 s.forEach(x=>{
  const split=rndSplit(D.rnd||[],x.year,x.rnd_project_spend||0);research.push(split.research);implementation.push(split.implementation);
  let fee=0,damage=0;
  allFirms.forEach(f=>{(f.yearly||[]).forEach(row=>{if(row.year!==x.year)return;Object.keys(row.cash_flows||{}).forEach(key=>{
   const amount=row.cash_flows[key];
   if(key==='staat:Patentgebühr')fee-=amount;
   else if(key.indexOf('schadenersatz:')===0&&amount<0)damage-=amount
  })})});
  fees.push(fee);damages.push(damage)
 });
 const colors=pal(),datasetDefs=[
  {label:'Forschung',data:research,backgroundColor:colors[0]+'cc'},
  {label:'Umsetzung',data:implementation,backgroundColor:colors[1]+'cc'},
  {label:'Patentgebühren',data:fees,backgroundColor:colors[3]+'cc'},
  {label:'Schadenersatz',data:damages,backgroundColor:css('--bad')+'cc'}
 ],datasets=datasetDefs;
 chart(canvasId,{type:'bar',data:{labels:s.map(x=>x.year),datasets:datasets},options:{scales:{x:{stacked:true,grid:{display:false}},y:{stacked:true,...fmtAxis('chf')}},plugins:{tooltip:{callbacks:{label:c=>c.dataset.label+': '+chf(c.parsed.y)}}}}})
}
function renderPatentOffences(){
 const rows=(D.offence_ledger||[]).filter(row=>row.offence==='patentverletzung'&&inRange(row.year));
 if(!rows.length){$('#st-patents').innerHTML=empty('Keine Patentverletzungen im Zeitraum.');return}
 $('#st-patents').innerHTML='<div class="table-wrap"><table id="st-patent-table"><thead><tr><th>Jahr</th><th>Firma</th><th>Inhaber</th><th>Vorteil</th><th>Busse</th><th>Schadenersatz</th><th>Urteil</th></tr></thead><tbody>'+rows.map(row=>'<tr><td class="num" data-value="'+row.year+'">'+row.year+'</td><td data-firm="'+esc(row.firm)+'">'+actorLabel(row.firm)+'</td><td>'+(row.holder?actorLabel(row.holder):'–')+'</td><td class="num" data-value="'+esc(row.gain)+'">'+chf(row.gain)+'</td><td class="num" data-value="'+esc(row.fine)+'">'+chf(row.fine)+'</td><td class="num" data-value="'+esc(row.compensation==null?row.damage:row.compensation)+'">'+chf(row.compensation==null?row.damage:row.compensation)+'</td><td><span class="badge '+(row.paid_off?'ok':'off')+'">'+(row.paid_off?'lohnend':'nicht lohnend')+'</span></td></tr>').join('')+'</tbody></table></div>';
 wireFirmLinks($('#st-patents'))
}
