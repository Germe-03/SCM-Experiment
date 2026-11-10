// Parse a rendered dashboard and exercise finance charts with a small DOM stub.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[2], 'utf8');
const D = JSON.parse(html.match(/<script id="dashboard-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
scripts.forEach(s => new vm.Script(s));
const source = scripts[0], nodes = new Map(), charts = new Map();
const $ = id => {if (!nodes.has(id)) nodes.set(id, {value:'',querySelectorAll:()=>[],querySelector:()=>null,scrollIntoView(){}}); return nodes.get(id)};
const range = {from: 1, to: 2}, S = {fmStage:new Set(['bank']),fmStatus:'all',fmSort:['profit',-1],tab:'firms'};
const periods=['week','month'].map(period=>({dataset:{period},setAttribute(){}}));
const context = {D, S, range, $, store:{get:(k,d)=>d,set(){}}, actorLabel:id=>D.firms[id]?.name||id, $$: selector => selector==='#sx-period button'?periods:[],
  inRange: y => y >= range.from && y <= range.to,
  sys: () => D.system.filter(x => x.year >= range.from && x.year <= range.to),
  firm: id => D.firms[id], fname: id => D.firms[id]?.name || id,
  esc: v => String(v ?? '').replaceAll('<', '&lt;'),
  pretty:String, EVENT:{}, REGION:{}, ARCH:{}, eventExtra:()=>'',
  FM_GROUPS:['retailer','restaurant','wholesaler','distributor','factory','bank'],
  fmGroup:f=>f?.channel==='restaurant'?'restaurant':f?.stage, fmGroupLabel:g=>g==='bank'?'Banken':g, catLabel:()=> '–',
  stageColor:()=>({}), kpi:(label,value)=>label+': '+value, sumBy:(a,k)=>a.reduce((n,r)=>n+(r[k]||0),0),
  renderFirmDetail:()=>{}, wireFirmLinks:()=>{}, openTab:tab=>{S.tab=tab},
  navigateView:change=>change(), showTab:tab=>{S.tab=tab}, hideStructure(){S.structure=false},
  nf: String, chf: String, pct: String, empty: String, fmtAxis: () => ({}),
  pal: () => ['red','blue','green','orange','purple','cyan','pink','black'],
  chart: (id, cfg) => charts.set(id, cfg), lines: (id, series) => charts.set(id, series),
  render: () => vm.runInContext('renderStocks()', context)};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function bankActors()'), source.indexOf('const DEC_GROUP=')), context);
vm.runInContext(source.slice(source.indexOf('function renderBanks()'), source.indexOf('function renderFinance()')), context);
vm.runInContext(source.slice(source.indexOf('// Aktienkurs im Reiter Vergleich')), context);
vm.runInContext('renderBanks();renderStocks()', context);
// Phase 23: ETF card in the stock tab.
if (D.etfs) {
  assert.match($('#etf-table').innerHTML, /<th>Grösste Firma<\/th>/);
  assert.match($('#etf-table').innerHTML, /data-etf="region:/);
  assert.ok(charts.get('etf-chart').data.datasets.length > 0);
  assert.match($('#etf-members').innerHTML, /Mitglieder: ETF /);
  vm.runInContext("S.etfKind='stage';renderEtfs()", context);
  assert.match($('#etf-table').innerHTML, /data-etf="stage:/);
  const anyFirm = D.etfs.definitions[0].members[0];
  assert.match(vm.runInContext(`etfMembership(${JSON.stringify(anyFirm)})`, context), /Enthalten in: ETF /);
}
assert.match($('#fi-banks').innerHTML, /Eigenkapitalquote/);
assert.equal(charts.get('fi-stocks').data.labels.length, 6);
assert.equal(charts.get('fi-stocks').data.datasets.length, 2);
assert.equal(charts.get('fi-stocks').data.datasets[1].yAxisID, 'y2');
assert.equal(charts.get('fi-stocks').options.scales.x.ticks.callback(0,0), 'Jahr 1');
assert.equal(charts.get('fi-stocks').options.plugins.tooltip.callbacks.title([{dataIndex:0}]), 'Jahr 1, Woche 1');
vm.runInContext('renderFirms()', context);
assert.match($('#fm-table').innerHTML, /bank:B1/);
assert.match($('#fm-stage').innerHTML, /Banken/);
assert.doesNotMatch($('#fm-table').innerHTML, /data-actor="retailer/);
assert.equal(($('#sx-top').innerHTML.match(/data-stock-add=/g)||[]).length, 10);
assert.equal(charts.get('sx-stages').data.datasets.length, 5);
const ids = Object.keys(D.stocks.prices).slice(0, 6);
ids.forEach(id=>vm.runInContext(`addStock(${JSON.stringify(id)})`,context));
assert.equal(S.stockFirms.length, 5);
assert.match($('#sx-selection-hint').textContent, /Entferne zuerst/);
assert.equal(charts.get('sx-compare').data.datasets.length, 6);
assert.equal(charts.get('sx-compare').data.datasets[0].data[0], 100);
periods[1].onclick();
assert.ok(charts.get('fi-stocks').data.labels.every(s=>s.includes('Monat')));
assert.equal(charts.get('sx-compare').data.datasets.length,6);
range.from = 2;
vm.runInContext(source.slice(source.indexOf('// Aktienkurs im Reiter Vergleich')), context);
vm.runInContext('renderBanks();renderStocks()', context);
assert.equal($('#fi-bank-year').textContent, 'Stand: Jahr 2');
assert.ok(charts.get('fi-stocks').data.labels.every(s => s.startsWith('Jahr 2')));
vm.runInContext(`renderStockChart('fd-price', [${JSON.stringify(ids[0])}], true, 'week', 'fd-stock-empty')`, context);
assert.equal(charts.get('fd-price').data.datasets.length, 2);
assert.equal(charts.get('fd-price').data.datasets[1].data[0],100);
assert.equal(vm.runInContext('bankRatio({equity:20,loans:80,deposits:80})',context),0.2);
vm.runInContext("renderBankDetail('B1')",context);
assert.match($('#fm-detail').innerHTML,/Zinsmarge/);
assert.match($('#fm-detail').innerHTML,/Marktanteil Einlagen/);
assert.match($('#bd-customer-list').innerHTML,/data-firm=/);
const bankEnd=D.banks.find(b=>b.bank_id==='B1'&&b.year===2);
['interest_expense','refinancing_cost','operating_cost','write_offs'].forEach((key,i)=>
  assert.equal(charts.get('bd-income').data.datasets[i+2].data[0],-(bankEnd[key]||0)));
const customer=D.banks.find(b=>b.bank_id==='B1'&&b.year===2).customer_ids[0];
assert.match(vm.runInContext(`firmBankLine(${JSON.stringify(customer)})`,context),/data-bank=/);
{const saved=D.banks,to=vm.runInContext('range.to',context);
 D.banks=[{bank_id:'BZ',name:'Zweit AG',year:to,customer_ids:['fx'],house_customer_ids:[]},{bank_id:'BH',name:'Haus AG',year:to,customer_ids:['fx','fy'],house_customer_ids:['fx','fy']}];
 assert.match(vm.runInContext("firmBankLine('fx')",context),/Hausbank: <a[^>]*data-bank="BH"[^>]*>Haus AG<\/a> · Zweitbank: <a[^>]*data-bank="BZ"/);
 assert.match(vm.runInContext("firmBankLine('fy')",context),/Zweitbank: keine/);
 assert.match(vm.runInContext("firmBankLine('nobody')",context),/Keine Kontoverbindung/);
 D.banks=saved;}
const link={dataset:{bank:'B1'}};
context.linkRoot={querySelectorAll:()=>[link]};
vm.runInContext('wireBankLinks(linkRoot)',context);
link.onclick({preventDefault(){},stopPropagation(){}});
assert.equal(S.fmFirm,'bank:B1'); assert.equal(S.tab,'firms');
const count=Object.keys(D.firms).length;
D.firms.B1={...D.firms[ids[0]],id:'B1'};
assert.equal(vm.runInContext("bankActors()['bank:B1'].stage",context),'bank');
assert.equal(Object.keys(D.firms).length,count+1);
// A failure before the selected range still identifies the first failed year.
D.banks.push({...D.banks[0], bank_id: 'failed', name: '<Failed>', year: 1, active: false},
             {...D.banks[0], bank_id: 'failed', name: '<Failed>', year: 2, active: false});
vm.runInContext('renderBanks()', context);
assert.match($('#fi-banks').innerHTML, /pleite seit Jahr 1/);
assert.match($('#fi-banks').innerHTML, /&lt;Failed>/);
range.to = 1; range.from = 1;
vm.runInContext('renderBanks()', context);
assert.equal($('#fi-bank-year').textContent, 'Stand: Jahr 1');
// Missing listing prices must stay gaps, never zero or a connected line.
D.stocks.prices[ids[0]][0] = null;
vm.runInContext(`renderStockChart('fd-price', [${JSON.stringify(ids[0])}], false)`, context);
assert.equal(charts.get('fd-price').data.datasets[0].data[0], null);
assert.equal(charts.get('fd-price').data.datasets[0].spanGaps, false);
// Controlled prices verify monthly closes, rankings and price-weighted returns.
D.meta.days_per_year=365;
D.stocks={days:[7,14,28,35,364],years:[1,1,1,1,1],index:[100,110,120,130,140],prices:{
  [ids[0]]:[1,2,3,4,5],[ids[1]]:[3,3,3,3,3]}};
D.firms[ids[0]].stage=D.firms[ids[1]].stage='factory';
vm.runInContext('renderStocks()',context);
assert.deepEqual(Array.from(vm.runInContext("stockPoints('month')",context)),[2,3,4]);
assert.equal(vm.runInContext("stockStageSeries('factory')[1]",context),125);
assert.ok($('#sx-top').innerHTML.indexOf(`data-stock-add="${ids[0]}"`)<$('#sx-top').innerHTML.indexOf(`data-stock-add="${ids[1]}"`));
D.stocks = {days: [], years: [], index: [], prices: {}}; D.banks = [];
vm.runInContext(source.slice(source.indexOf('// Aktienkurs im Reiter Vergleich')), context);
vm.runInContext('renderBanks();renderStocks()', context);
assert.match($('#fi-banks').innerHTML, /Keine Bankberichte/);
assert.match($('#fi-stock-empty').textContent, /Keine Börsenkurse/);
vm.runInContext(source.slice(source.indexOf('const FLOW_REASON='), source.indexOf('const sumV=')), context);
const fid = ids[0];
D.firms[fid].yearly = [{year: 1, cash_flows: {'bankpleite:B1': -70, 'bank:Schuldenschnitt': 20, 'unknown:x': -5}}];
const groups = vm.runInContext(`flowGroups(${JSON.stringify(fid)},1)`, context);
assert.equal(groups.bank.out[0].v, 70);
assert.equal(groups.bank.out[0].info, 'Verlust bei Bankpleite (nur 30 % gesichert)');
assert.equal(groups.bank.in[0].v, 20);
assert.equal(groups.beteiligungen.out.length, 0);
assert.equal(groups.betrieb.out[0].v, 5);
context.CAT={beer:'Bier',wine:'Wein',spirits:'Spirituosen'};
context.stageLabel=()=> 'Grosshandel';
const partner=ids[1];
D.firms[fid].yearly=[{year:1,revenue:100,purchase_cost:300,paid_to:{[partner]:300},
 paid_items:{[partner+'|beer']:{chf:100,units:10},[partner+'|wine']:{chf:200,units:8}},
 sold_items:{'konsumenten|beer':{chf:60,units:5},'konsumenten|wine':{chf:40,units:2}}}];
const products=vm.runInContext(`flowGroups(${JSON.stringify(fid)},1)`,context);
assert.equal(products.lieferanten.out.length,2);
assert.equal(products.lieferanten.out[0].v,200);
assert.equal(products.lieferanten.out[0].units,8);
assert.equal(products.lieferanten.out[0].firm,partner);
assert.match(products.lieferanten.out[0].info,/Wein/);
assert.equal(products.kunden.in.length,2);
assert.equal(products.kunden.in[0].n,'Konsumenten');
console.log('Dashboard syntax, stocks, bank details, filters, navigation and bank flows passed.');
