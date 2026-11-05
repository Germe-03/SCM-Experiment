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
