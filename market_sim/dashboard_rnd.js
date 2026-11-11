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
function rndCategoryNames(){return {beer:'Bier',wine:'Wein',spirits:'Spirituosen',softdrinks:'Softdrinks',water:'Wasser'}}
function rndEffectText(st){
 const e=st.effect||0,p=Math.round(e*1000)/10+' %',comp={malt:'Malz',hops:'Hopfen',packaging:'Verpackung',energy:'Energie',sugar:'Zucker',fruit:'Fruchtkonzentrat',co2:'CO2',pet:'PET/Dosen'};
 switch(st.kind){
  case 'component_reduction':return (comp[st.component]||'Stückkosten')+'kosten −'+p;
  case 'cost_reduction':return 'Stückkosten (Rohstoffe) −'+p;
  case 'transport_efficiency':return 'Transportkosten −'+p;
  case 'storage_automation':return 'Lagerkosten −'+p;
  case 'robotics':return 'Personal −'+p+', Kapazität unverändert';
  case 'productivity':return 'Kapazität +'+p;
  case 'new_brand':return 'Neue Marke (Premium)';
  case 'alkoholfrei':return 'Neue Marke (alkoholfrei)';
  case 'new_category':return 'Neue Marke ('+(rndCategoryNames()[st.adds_category]||st.adds_category||'')+')';
  case 'reputation':return 'Ruf +'+p;
  case 'awareness':return 'Bekanntheit +'+p;
  case 'margin':return 'Marge +'+p;
  case 'maturation':return 'Reifezeit −'+p;
  default:return String(st.kind||'')
 }
}
function rndTooltipHtml(tree,name){
 const stages=D.rnd_trees&&D.rnd_trees[tree]||[],st=stages.find(x=>x.name===name);if(!st)return '';
 const req=(st.requires||[]).map(r=>esc(rndLabel(tree,r))).join(', ')||'keine';
 return '<b>'+esc(st.label||st.name)+'</b><br>Wirkung: '+esc(rndEffectText(st))+'<br>Patentierbar: '+(st.patentable?'ja':'nein')+'<br>Forschung: '+chf(st.cost||0)+', '+esc(st.duration_days)+' Tage, Erfolg '+Math.round((st.success_probability||0)*100)+' %<br>Umsetzung: '+chf(st.implementation_cost||0)+', '+esc(st.implementation_days)+' Tage<br>Voraussetzungen: '+req
}
function rndTooltipInstall(){
 if(window.__rndTip)return;window.__rndTip=true;
 let tip=null;
 const hide=()=>{if(tip)tip.style.display='none'};
 document.addEventListener('mouseover',e=>{
  const g=e.target.closest&&e.target.closest('g[data-stage][data-tree]');if(!g){hide();return}
  if(!tip){tip=document.createElement('div');tip.id='rnd-tooltip';tip.style.cssText='position:fixed;z-index:1000;max-width:320px;padding:8px 10px;background:var(--card,#fff);color:var(--ink,#000);border:1px solid var(--line,#ccc);border-radius:8px;box-shadow:0 4px 14px rgba(0,0,0,.25);font-size:12px;line-height:1.5;pointer-events:none';document.body.appendChild(tip)}
  tip.innerHTML=rndTooltipHtml(g.dataset.tree,g.dataset.stage);tip.style.display='block'
 });
 document.addEventListener('mousemove',e=>{if(!tip||tip.style.display==='none')return;tip.style.left=Math.min(e.clientX+14,window.innerWidth-340)+'px';tip.style.top=Math.min(e.clientY+14,window.innerHeight-tip.offsetHeight-8)+'px'});
 document.addEventListener('mouseout',e=>{if(!e.relatedTarget)hide()})
}
if(typeof document!=='undefined'&&document.addEventListener)rndTooltipInstall();
function rndTreeSvg(tree,firmId=null,catFilter=null){
 let stages=D.rnd_trees&&D.rnd_trees[tree];if(!stages)return '';
 if(catFilter)stages=stages.filter(x=>!(x.categories||[]).length||x.categories.includes(catFilter));
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
 const branchNames={automation:'Automation',rezeptur:'Rezeptur',verpackung:'Verpackung',energie:'Energie',marke:'Marke',wein:'Wein',qualitaet:'Qualität',logistik:'Logistik',lager:'Lager',kunden:'Kunden'};
 const colKey=stage=>(stage.branch||'sonstige')+'|'+((stage.categories||[]).length?stage.categories.join(','):'');
 const columns=[],positions={},slots={},rowsAt={};let maxDepth=0;
 stages.forEach(stage=>{const k=colKey(stage);if(!columns.includes(k))columns.push(k)});
 const order=[];columns.forEach(k=>{const b=k.split('|')[0];if(!order.includes(b))order.push(b)});
 columns.sort((a,b)=>{const d=order.indexOf(a.split('|')[0])-order.indexOf(b.split('|')[0]);return d||(a<b?-1:a>b?1:0)});
 const colW=220,nodeW=200;
 stages.forEach(stage=>{const d=depths[stage.name],c=columns.indexOf(colKey(stage)),sk=c+'/'+d;slots[sk]=slots[sk]==null?0:slots[sk]+1;slots[stage.name]=slots[sk];rowsAt[d]=Math.max(rowsAt[d]||1,slots[sk]+1);maxDepth=Math.max(maxDepth,d)});
 const rowStart={};let acc=0;for(let d=0;d<=maxDepth;d++){rowStart[d]=acc;acc+=rowsAt[d]||1}
 stages.forEach(stage=>{const d=depths[stage.name],c=columns.indexOf(colKey(stage));positions[stage.name]={x:10+c*colW,y:44+(rowStart[d]+slots[stage.name])*120}});
 const branches=columns,width=20+columns.length*colW,height=44+acc*120+30,progress=rndProgress(tree,firmId),suffix=String(tree)+'-'+String(firmId||'sector'),marker='rnd-arrow-'+suffix.replace(/[^a-zA-Z0-9_-]/g,'_');
 let svg='<svg width="100%" viewBox="0 0 '+width+' '+height+'" style="min-width:'+width+'px" role="img" aria-label="'+esc(rndTreeNames()[tree]||tree)+'">';
 branches.forEach((key,i)=>{const parts=key.split('|'),b=parts[0],cats=parts[1]?' ('+parts[1].split(',').map(c=>rndCategoryNames()[c]||c).join(', ')+')':'';svg+='<text data-branch="'+esc(b)+'" x="'+(10+i*colW+nodeW/2)+'" y="22" text-anchor="middle" fill="var(--ink)" font-size="13" font-weight="600">'+esc((branchNames[b]||(b.charAt(0).toUpperCase()+b.slice(1)))+cats)+'</text>'});
 svg+='<defs><marker id="'+esc(marker)+'" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="var(--muted)"/></marker></defs>';
 stages.forEach(stage=>(stage.requires||[]).filter(name=>byName[name]).forEach(name=>{
  const from=positions[name],to=positions[stage.name],cross=(byName[name].branch||'')!==(stage.branch||''),x1=from.x+nodeW/2,y1=from.y+76,x2=to.x+nodeW/2,y2=to.y-2,mid=(y1+y2)/2,edge=esc(name).replace(/&gt;/g,'>')+'>'+esc(stage.name).replace(/&gt;/g,'>');
  svg+='<path data-edge="'+edge+'" d="M'+x1+' '+y1+' C'+x1+' '+mid+' '+x2+' '+mid+' '+x2+' '+y2+'" fill="none" stroke="var(--muted)" stroke-width="'+(cross?'1':'1.5')+'"'+(cross?' stroke-dasharray="4 3" opacity=".55"':'')+' marker-end="url(#'+esc(marker)+')"/>'
 }));
 stages.forEach(stage=>{
  const name=stage.name,pos=positions[name],info=progress[name],state=firmId?(info.firms[firmId]||'open'):(info.implemented?'implemented':info.researched?'researched':'open');
  const patent=rndPatent(tree,name,range.to),active=patent&&patent.active,expired=patent&&!patent.active;
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
  svg+='<g data-stage="'+esc(name)+'" data-tree="'+esc(tree)+'" data-state="'+state+'"'+(expired?' data-patent="expired"':'')+'><rect x="'+pos.x+'" y="'+pos.y+'" width="'+nodeW+'" height="76" rx="9" style="'+style+'"/>'+(expired?'<rect x="'+(pos.x-3)+'" y="'+(pos.y-3)+'" width="'+(nodeW+6)+'" height="82" rx="11" fill="none" stroke="#8b5cf6" stroke-width="2" stroke-dasharray="5 3"/>':'')+'<text x="'+(pos.x+10)+'" y="'+(pos.y+19)+'" fill="var(--ink)" font-size="12">'+esc(label)+'</text>';
  lines.forEach((line,i)=>{svg+='<text x="'+(pos.x+10)+'" y="'+(pos.y+36+i*14)+'" fill="var(--muted)" font-size="11">'+line+'</text>'});
  svg+='</g>'
 });
 return '<div style="overflow-x:auto">'+svg+'</svg></div>'
}
function renderRndTrees(){
 const names=rndTreeNames(),trees=Object.keys(names).filter(tree=>D.rnd_trees&&D.rnd_trees[tree]);
 if(!trees.length){$('#rd-tree-chips').innerHTML='';$('#rd-tree').innerHTML=empty('In diesem Lauf gibt es keine Forschungsbäume.');return}
 let tree=S.rdTree||store.get('rd-tree','factory');if(!trees.includes(tree))tree=trees[0];S.rdTree=tree;
 $('#rd-tree-chips').innerHTML=trees.map(key=>'<button class="chip" data-tree="'+esc(key)+'" aria-pressed="'+(key===tree?'true':'false')+'">'+esc(names[key])+'</button>').join('');
 $('#rd-tree-chips').onclick=e=>{const b=e.target.closest('button[data-tree]');if(!b)return;S.rdTree=b.dataset.tree;store.set('rd-tree',S.rdTree);renderRndTrees()};
 const cats=[];(D.rnd_trees[tree]||[]).forEach(x=>(x.categories||[]).forEach(c=>{if(!cats.includes(c))cats.push(c)}));
 let cat=S.rdCat||'';if(cat&&!cats.includes(cat))cat='';S.rdCat=cat;
 const filter=cats.length?'<p class="hint">Kategorie: <select id="rd-cat"><option value="">alle</option>'+cats.map(c=>'<option value="'+esc(c)+'"'+(c===cat?' selected':'')+'>'+esc(rndCategoryNames()[c]||c)+'</option>').join('')+'</select></p>':'';
 $('#rd-tree').innerHTML=filter+'<p class="hint"><span style="color:var(--good)">■</span> umgesetzt · <span style="color:var(--c4)">■</span> erforscht · <span style="color:var(--muted)">■</span> offen · <span style="color:var(--accent)">■</span> Patent aktiv · <span style="color:#8b5cf6">■</span> Patent abgelaufen · Stand Ende Jahr '+range.to+'</p>'+rndTreeSvg(tree,null,cat||null);
 const sel=$('#rd-cat');if(sel)sel.onchange=()=>{S.rdCat=sel.value;renderRndTrees()}
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
