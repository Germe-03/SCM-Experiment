function fsNumber(value){return value==null?0:Number(value)||0}
function fsMoney(value){return chf(fsNumber(value))}
function fsExpense(value){return chf(-Math.abs(fsNumber(value)))}
function fsRow(label,value,bold=false,extraStyle=''){
 const style=(bold?'font-weight:700;':'')+extraStyle;
 return '<tr><td'+(style?' style="'+style+'"':'')+'>'+esc(label)+'</td><td style="text-align:right;'+style+'">'+value+'</td></tr>'
}
function fsSection(label){return '<tr><td colspan="2" style="font-weight:700">'+esc(label)+'</td></tr>'}
function fsHintRow(){return '<tr><td>Keine Abschlüsse vorhanden</td></tr>'}
function renderStatements(){
 const state=typeof S==='object'&&S?S:null,financials=D.financials||{},firmSelect=$('#fs-firm'),yearSelect=$('#fs-year');
 const firms=Object.keys(financials).filter(id=>Array.isArray(financials[id])&&financials[id].length).map(id=>({id:id,label:String(fname(id)||id)})).sort((a,b)=>a.label.localeCompare(b.label)||a.id.localeCompare(b.id));
 const previousFirm=state&&state.fsFirm!=null?String(state.fsFirm):'';
 let firmId=firms.some(x=>x.id===previousFirm)?previousFirm:(firms.length?firms[0].id:'');
 firmSelect.innerHTML=firms.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.label)+'</option>').join('');
 firmSelect.value=firmId;
 if(state)state.fsFirm=firmId;
 firmSelect.onchange=()=>{
  if(typeof S==='object'&&S)S.fsFirm=firmSelect.value;
  renderStatements()
 };
 const reports=firmId?(financials[firmId]||[]).slice().sort((a,b)=>Number(a.year)-Number(b.year)):[];
 let years=reports.filter(r=>Number(r.year)>=Number(range.from)&&Number(r.year)<=Number(range.to));
 if(!years.length)years=reports.slice();
 const previousYear=state&&state.fsYear!=null?String(state.fsYear):'';
 let selectedYear=years.some(r=>String(r.year)===previousYear)?previousYear:(years.length?String(years[years.length-1].year):'');
 yearSelect.innerHTML=years.map(r=>'<option value="'+esc(r.year)+'">'+esc(r.year)+'</option>').join('');
 yearSelect.value=selectedYear;
 if(state)state.fsYear=selectedYear;
 yearSelect.onchange=()=>{
  if(typeof S==='object'&&S)S.fsYear=yearSelect.value;
  renderStatements()
 };
 const report=years.find(r=>String(r.year)===selectedYear);
 if(!report){
  $('#fs-income').innerHTML=fsHintRow();
  $('#fs-balance').innerHTML=fsHintRow();
  $('#fs-cash').innerHTML=fsHintRow();
  $('#fs-ratios').innerHTML=fsHintRow();
 }else{
  const income=report.income_statement||{};
  const incomeRows=[
   fsRow('Umsatz',fsMoney(income.revenue)),
   fsRow('– Warenaufwand',fsExpense(income.cogs)),
   fsRow('= Bruttogewinn',fsMoney(income.gross_profit),true),
   fsRow('– Personalaufwand',fsExpense(income.wages)),
   fsRow('– Miete und Fixkosten',fsExpense(income.rent_fixed)),
   fsRow('– Umschlag und Transport',fsExpense(income.handling)),
   fsRow('– Lager',fsExpense(income.storage)),
   fsRow('– Marketing',fsExpense(income.marketing)),
   fsRow('– Forschung',fsExpense(income.research)),
   fsRow('– Übriger Betriebsaufwand',fsExpense(income.other_opex)),
   fsRow('= EBITDA',fsMoney(income.ebitda),true),
   fsRow('– Abschreibungen',fsExpense(income.depreciation)),
   fsRow('= EBIT',fsMoney(income.ebit),true),
   fsRow('– Zinsen',fsExpense(income.interest)),
   fsRow('= Ergebnis vor Steuern',fsMoney(income.ebt),true),
   fsRow('– Steuern',fsExpense(income.taxes)),
   fsRow('= Reingewinn',fsMoney(income.net_income),true,'color:var(--'+(fsNumber(income.net_income)>=0?'good':'bad')+');')
  ];
  $('#fs-income').innerHTML=incomeRows.join('');
  const balance=report.balance_sheet||{},assets=balance.assets||{},liabilities=balance.liabilities||{};
  $('#fs-balance').innerHTML=[
   fsSection('Aktiven'),
   fsRow('Kasse',fsMoney(assets.cash)),
   fsRow('Vorräte',fsMoney(assets.inventory)),
   fsRow('Lastwagen',fsMoney(assets.trucks)),
   fsRow('Standorte',fsMoney(assets.sites)),
   fsRow('Beteiligungen',fsMoney(assets.participations)),
   fsRow('Wertschriften',fsMoney(assets.securities)),
   fsRow('Total Aktiven',fsMoney(assets.total),true),
   fsSection('Passiven'),
   fsRow('Bankdarlehen',fsMoney(liabilities.loans)),
   fsRow('Kontokorrent',fsMoney(liabilities.overdraft)),
   fsRow('Übrige Verbindlichkeiten',fsMoney(Math.max(0,fsNumber(liabilities.other)-fsNumber(liabilities.overdraft)))),
   fsRow('Fremdkapital total',fsMoney(liabilities.total),true),
   fsRow('Eigenkapital',fsMoney(balance.equity)),
   fsRow('Total Passiven',fsMoney(balance.total),true)
  ].join('');
  const cash=report.cash_flow||{};
  $('#fs-cash').innerHTML=[
   fsRow('Betrieb',fsMoney(cash.operating)),
   fsRow('Investitionen',fsMoney(cash.investing)),
   fsRow('Finanzierung',fsMoney(cash.financing)),
   fsRow('Dividenden erhalten',fsMoney(cash.dividends_received)),
   fsRow('Dividenden bezahlt',fsMoney(-fsNumber(cash.dividends_paid))),
   fsRow('Veränderung Geld',fsMoney(cash.change),true)
  ].join('');
  const ratios=report.ratios||{},calculation=report.calculation||{},calcValue=value=>nf(fsNumber(value),2)+' CHF';
  $('#fs-ratios').innerHTML=[
   fsRow('Bruttomarge',pct(fsNumber(ratios.gross_margin))),
   fsRow('EBIT-Marge',pct(fsNumber(ratios.ebit_margin))),
   fsRow('Eigenkapitalquote',pct(fsNumber(ratios.equity_ratio))),
   fsRow('Liquidität',nf(fsNumber(ratios.liquidity),2)),
   fsRow('Eigenkapitalrendite',pct(fsNumber(ratios.roe))),
   fsSection('Kalkulation pro Flasche'),
   fsRow('Einstandspreis',calcValue(calculation.purchase_price)),
   fsRow('Bezugskosten',calcValue(calculation.procurement_costs)),
   fsRow('Bezugspreis',calcValue(calculation.landed_cost)),
   fsRow('Gemeinkosten',calcValue(calculation.overhead)),
   fsRow('Selbstkosten',calcValue(calculation.full_cost)),
   fsRow('Verkaufspreis',calcValue(calculation.sell_price)),
   fsRow('Gewinn pro Flasche',calcValue(calculation.profit)),
   fsRow('Marge',nf(fsNumber(calculation.margin_pct),1)+' %'),
   fsRow('Break-even-Preis',calcValue(calculation.break_even_price)),
   fsRow('Flaschen pro Tag',nf(fsNumber(calculation.bottles_per_day)))
  ].join('')
 }
 const colors=pal();
 chart('fs-chart',{
  type:'bar',
  data:{
   labels:years.map(r=>r.year),
   datasets:[
    {label:'Umsatz',data:years.map(r=>fsNumber((r.income_statement||{}).revenue)),backgroundColor:colors[0]},
    {label:'EBIT',data:years.map(r=>fsNumber((r.income_statement||{}).ebit)),backgroundColor:colors[1]},
    {label:'Reingewinn',data:years.map(r=>fsNumber((r.income_statement||{}).net_income)),backgroundColor:colors[2]}
   ]
  },
  options:{responsive:true,maintainAspectRatio:false,scales:{y:{ticks:{callback:v=>chf(v)}}}}
 })
}
