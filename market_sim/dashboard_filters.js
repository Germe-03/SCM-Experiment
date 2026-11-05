// Shared column filters. State belongs to a stable table ID, not to its DOM rows.
const tableFilters = new Map();
const filterTables = new Set(['fm-table','rd-table','ev-table','fi-banks','sx-top','fi-holdings']);
let filterPopup = null;
function closeColumnFilter(){if(filterPopup){const {panel,button}=filterPopup;panel.remove();button.setAttribute('aria-expanded','false');filterPopup=null}}
function columnNumber(cell){
 if(!cell)return null;
 if(cell.dataset.value!==undefined){const v=Number(cell.dataset.value);return cell.dataset.value!==''&&Number.isFinite(v)?v:null}
 const text=cell.textContent.trim().replace(/[’'\s]/g,'').replace('−','-');
 if(!/^[+-]?\d+(?:[.,]\d+)?(?:%|CHF|Mio\.CHF|Mrd\.CHF|Mia\.CHF)?$/.test(text))return null;
 return parseFloat(text.replace(',','.'))*((text.includes('Mrd.')||text.includes('Mia.'))?1e9:text.includes('Mio.')?1e6:1);
}
function columnMatches(value,filter){
 if(!filter)return true;
 if(filter.values)return filter.values.has(value);
 return value!=null&&(filter.min===''||value>=Number(filter.min))&&(filter.max===''||value<=Number(filter.max));
}
function filteredTableMetrics(table,rows){
 if(table.id.startsWith('ledger-')){const value=table.closest('.card')?.querySelector('.kpi b');if(value)value.textContent=nf(rows.filter(r=>r.dataset.paidOff==='true').length)+' von '+nf(rows.length)}
 if(table.id==='rd-table'){
  const cards=$$('#rd-kpis .kpi');
  if(cards[1]){cards[1].querySelector('b').textContent=nf(rows.length);cards[1].querySelector('small').textContent=rows.length?pct(rows.filter(r=>r.dataset.success==='true').length/rows.length)+' erfolgreich':''}
  if(cards[3])cards[3].querySelector('b').textContent=nf(rows.filter(r=>r.dataset.newBrand==='true').length);
 }
}
function applyColumnFilters(table,state){
 const rows=state.rows.filter(row=>state.columns.every((col,i)=>columnMatches(col.numeric?columnNumber(row.cells[i]):row.cells[i].textContent.trim(),state.filters.get(i))));
 const visible=new Set(rows),limit=table.id==='ev-table'?S.evLimit:Infinity;let count=0;
 state.rows.forEach(row=>{row.hidden=!visible.has(row)||count>=limit;if(visible.has(row))count++});
 const active=state.filters.size>0;
 state.summary.hidden=!active;
 state.summary.querySelector('span').textContent=`${nf(rows.length)} von ${nf(state.rows.length)} Zeilen`;
 state.columns.forEach((col,i)=>{if(col.button){col.button.classList.toggle('active',state.filters.has(i));col.button.setAttribute('aria-pressed',String(state.filters.has(i)))}});
 if(table.id==='ev-table'){$('#ev-more').hidden=rows.length<=limit;$('#ev-more').textContent=`Weitere anzeigen (${nf(Math.max(0,rows.length-limit))} übrig)`}
 filteredTableMetrics(table,rows);
}
function openColumnFilter(table,state,index,button){
 if(filterPopup?.button===button){closeColumnFilter();return}closeColumnFilter();
 const col=state.columns[index],panel=document.createElement('div');panel.className='column-filter-panel';panel.setAttribute('role','group');panel.setAttribute('aria-label','Filter für '+col.label);
 const current=state.filters.get(index);
 const update=filter=>{if(filter)state.filters.set(index,filter);else state.filters.delete(index);applyColumnFilters(table,state)};
 if(col.numeric){
  panel.innerHTML='<label>von<input type="number" step="any" data-bound="min"></label><label>bis<input type="number" step="any" data-bound="max"></label>';
  panel.querySelectorAll('input').forEach(input=>{input.value=current?.[input.dataset.bound]??'';input.setAttribute('aria-label',col.label+' '+(input.dataset.bound==='min'?'von':'bis'));input.oninput=()=>{const min=panel.querySelector('[data-bound=min]').value,max=panel.querySelector('[data-bound=max]').value;update(min===''&&max===''?null:{min,max})}});
 }else{
  const options=[...new Set([...state.rows.map(r=>r.cells[index].textContent.trim()),...(current?.values||[])])].sort((a,b)=>a.localeCompare(b,'de-CH'));
  let selected=new Set(current?.values??options);
  panel.innerHTML='<input type="search" aria-label="Filterwerte suchen" placeholder="Suchen …"><div class="filters"><button type="button" class="btn" data-all>alle</button><button type="button" class="btn" data-none>keine</button></div><div class="column-options"></div>';
  const list=panel.querySelector('.column-options');
  const save=()=>update(selected.size===options.length?null:{values:new Set(selected)});
  options.forEach(value=>{const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=selected.has(value);input.onchange=()=>{input.checked?selected.add(value):selected.delete(value);save()};label.append(input,document.createTextNode(value||'(leer)'));list.append(label)});
  panel.querySelector('[type=search]').oninput=e=>{const q=e.target.value.toLocaleLowerCase('de-CH');list.querySelectorAll('label').forEach(label=>label.hidden=!label.textContent.toLocaleLowerCase('de-CH').includes(q))};
  const select=all=>{selected=new Set(all?options:[]);list.querySelectorAll('input').forEach(input=>input.checked=all);save()};
  panel.querySelector('[data-all]').onclick=()=>select(true);panel.querySelector('[data-none]').onclick=()=>select(false);
 }
 const done=document.createElement('button');done.className='btn';done.textContent='Schliessen';done.onclick=()=>{closeColumnFilter();button.focus()};panel.append(done);
 document.body.append(panel);const rect=button.getBoundingClientRect();panel.style.left=Math.max(8,Math.min(rect.left,window.innerWidth-290))+'px';panel.style.top=Math.min(rect.bottom+4,Math.max(8,window.innerHeight-340))+'px';
 button.setAttribute('aria-expanded','true');filterPopup={panel,button};panel.querySelector('input,button').focus();
 panel.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();closeColumnFilter();button.focus()}});
}
function installColumnFilters(){
 document.querySelectorAll('table').forEach((table,index)=>{
  const headers=[...(table.tHead?.rows[0]?.cells||[])],rows=[...(table.tBodies[0]?.rows||[])].filter(row=>row.cells.length===headers.length&&row.cells[0]?.colSpan===1);
  if(!headers.length)return;
  if(!table.id)table.id='table-'+(table.closest('[id]')?.id||'dashboard')+'-'+index;
  if(!filterTables.has(table.id)&&!table.id.startsWith('ledger-')&&rows.length<=15&&!tableFilters.has(table.id))return;
  let state=tableFilters.get(table.id);
  if(state?.body===table.tBodies[0]&&headers[0].querySelector('.column-filter-button'))return;
  if(filterPopup?.button&&!filterPopup.button.isConnected)closeColumnFilter();
  state={filters:state?.filters||new Map(),sort:state?.sort,body:table.tBodies[0],rows,columns:[],summary:null};tableFilters.set(table.id,state);
  const prior=table.parentElement.previousElementSibling;
  if(prior?.dataset.filterSummary===table.id)prior.remove();
  const summary=document.createElement('div');summary.className='filter-summary';summary.dataset.filterSummary=table.id;summary.innerHTML='<span role="status"></span> <button type="button" class="btn">Filter zurücksetzen</button>';table.parentElement.before(summary);state.summary=summary;
  summary.querySelector('button').onclick=()=>{closeColumnFilter();state.filters.clear();applyColumnFilters(table,state)};
  headers.forEach((th,i)=>{
   const label=th.textContent.trim(),numeric=th.classList.contains('num')||(/^(Jahr|Tag|Start|Ende|Kunden|Gewinn|Busse|Schaden|Netto|Kosten|Kurs|Veränderung|Börsenwert|Eigenkapital|Eigenkapitalquote|Kredite|Einlagen|Abschreibungen|Abgelehnte Kredite|Gebühren)$/.test(label))||(rows.length>0&&rows.every(row=>columnNumber(row.cells[i])!=null));
   const col={label,numeric};state.columns.push(col);if(table.id==='ev-table'&&label==='Details')return;
   const sort=document.createElement('button');sort.type='button';sort.className='column-sort';sort.textContent=label;
   const oldClick=th.onclick;th.onclick=null;th.onkeydown=null;th.removeAttribute('tabindex');th.replaceChildren(sort);
   sort.onclick=e=>{closeColumnFilter();if(oldClick){oldClick.call(th,e);return}const direction=state.sort?.index===i?-state.sort.direction:1;state.sort={index:i,direction};sortColumnRows(table,state)};
   const button=document.createElement('button');button.type='button';button.className='column-filter-button';button.setAttribute('aria-label','Filter für '+label);button.setAttribute('aria-expanded','false');button.innerHTML='<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M2 3h12L9 9v4l-2 1V9z" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';
   button.onclick=e=>{e.stopPropagation();openColumnFilter(table,state,i,button)};th.append(button);col.button=button;
  });
  if(state.sort)sortColumnRows(table,state);else applyColumnFilters(table,state);
 });
}
function sortColumnRows(table,state){const {index,direction}=state.sort,col=state.columns[index];state.rows.sort((a,b)=>{const x=col.numeric?columnNumber(a.cells[index]):a.cells[index].textContent,y=col.numeric?columnNumber(b.cells[index]):b.cells[index].textContent;return x==null?y==null?0:1:y==null?-1:direction*(col.numeric?x-y:x.localeCompare(y,'de-CH'))});state.rows.forEach(row=>state.body.append(row));applyColumnFilters(table,state)}
document.addEventListener('pointerdown',e=>{if(filterPopup&&!filterPopup.panel.contains(e.target)&&!filterPopup.button.contains(e.target))closeColumnFilter()});
// Observe subtree replacements as individual views also redraw from chips and search.
const filterObserver=new MutationObserver(()=>{filterObserver.disconnect();installColumnFilters();filterObserver.observe(document.querySelector('main'),{childList:true,subtree:true})});
filterObserver.observe(document.querySelector('main'),{childList:true,subtree:true});
installColumnFilters();
