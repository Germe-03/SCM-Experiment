// Run after the rendered dashboard in a browser (uses the real DOM).
(async()=>{
 const assert=(value,message)=>{if(!value)throw new Error(message)};
 const settle=()=>new Promise(resolve=>setTimeout(resolve,0));
 const visible=table=>[...table.tBodies[0].rows].filter(row=>!row.hidden&&row.cells[0].colSpan===1);
 const clickFilter=(table,label)=>table.querySelector(`[aria-label="Filter für ${label}"]`).click();
 try{
  openTab('firms');await settle();const firms=$('#fm-table');
  assert(firms.querySelectorAll('.column-filter-button').length===10,'Firm columns');
  clickFilter(firms,'Stufe');document.querySelector('[data-none]').click();
  assert(visible(firms).length===0,'No text values selected');
  document.querySelector('[data-all]').click();assert(visible(firms).length>0,'All text values');
  const search=document.querySelector('.column-filter-panel input[type=search]');search.value='Banken';search.dispatchEvent(new Event('input'));
  assert([...document.querySelectorAll('.column-options label')].filter(l=>!l.hidden).length===1,'Search options');
  document.querySelector('[data-none]').click();const bank=[...document.querySelectorAll('.column-options label')].find(l=>l.textContent==='Banken');bank.querySelector('input').click();
  assert(visible(firms).every(r=>r.cells[1].textContent==='Banken'),'Text column selection');
  closeColumnFilter();clickFilter(firms,'Gewinn im Zeitraum');
  const input=document.querySelector('[data-bound=min]');input.value='100000000000000';input.dispatchEvent(new Event('input'));
  assert(visible(firms).length===0,'Numeric intersection');closeColumnFilter();
  renderFirms();await settle();assert(visible(firms).length===0,'Filters survive redraw');
  $('#to').value=1;$('#to').dispatchEvent(new Event('change'));await settle();assert(visible(firms).length===0,'Filters survive period change');
  document.querySelector('[data-filter-summary="fm-table"] button').click();assert(visible(firms).length>0,'Reset all columns');
  openStructure();assert($('#structure').open,'Structure opens');
  assert($('#ms-timeline').textContent.includes('Banken'),'Bank timeline group');
  const bar=$('#ms-timeline').querySelector('[data-firm^="bank:"]');bar.dispatchEvent(new MouseEvent('click',{bubbles:true}));
  assert(!$('#structure').open&&S.fmFirm.startsWith('bank:'),'Bank bar opens detail');
  restoreView(viewIndex-1);await settle();assert($('#structure').open,'Back restores dialog');
  $('#structure').dispatchEvent(new Event('cancel',{cancelable:true}));assert(!$('#structure').open,'Escape closes dialog');
  // Explicit fixtures ensure filter checks are independent of rare simulation events.
  D.events.push({year:1,day:1,event:'bank_failed',firm:D.banks[0].bank_id,details:'Bank test'});
  openTab('events');S.evTypes=new Set(['bank_failed']);renderEvents();await settle();
  const events=$('#ev-table');assert(events.querySelectorAll('.column-filter-button').length===4,'Details is not filterable');
  assert(events.querySelector('[data-bank]')?.textContent===D.banks[0].name,'Bank name is linked');
  clickFilter(events,'Art');document.querySelector('[data-none]').click();assert(visible(events).length===0,'Event column filter');
  closeColumnFilter();$('#ev-all').click();await settle();assert(visible(events).length===0,'Chips retain column filter');
  document.querySelector('[data-filter-summary="ev-table"] button').click();assert(visible(events).length>0,'Event reset');
  D.offence_ledger=[{firm:Object.keys(D.firms)[0],year:1,offence:'pfusch',gain:100,fine:0,damage:0,net:100,paid_off:true},{firm:Object.keys(D.firms)[1],year:1,offence:'pfusch',gain:100,fine:200,damage:0,net:-100,paid_off:false}];
  openTab('state');await settle();const ledger=$('#ledger-state');clickFilter(ledger,'Urteil');document.querySelector('[data-none]').click();
  const profitable=[...document.querySelectorAll('.column-options label')].find(l=>l.textContent==='lohnend');profitable.querySelector('input').click();
  assert(ledger.closest('.card').querySelector('.kpi b').textContent==='1 von 1','Filtered ledger KPI');closeColumnFilter();
  for(const [tab,id] of [['finance','fi-banks'],['finance','fi-holdings'],['stocks','sx-top'],['rnd','rd-table']]){openTab(tab);await settle();assert($('#'+id).querySelector('.column-filter-button'),id+' filters')}
  document.body.dataset.checkResult='passed';
 }catch(error){document.body.dataset.checkResult='FAILED: '+error.stack}
})();
