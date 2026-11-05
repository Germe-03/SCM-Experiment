// Exercise comparison calculations and SVG output without a browser dependency.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const start = source.indexOf('const CMP_METRICS=');
const end = source.indexOf('// --- Lieferkette', start);
const nodes = new Map();
const $ = id => {
  if (!nodes.has(id)) nodes.set(id, {value: '', innerHTML: '', textContent: ''});
  return nodes.get(id);
};
const firms = Object.fromEntries(Array.from({length: 8}, (_, i) => [`f${i}`, {
  id: `f${i}`, name: `Firm <${i}>`, stage: 'retailer', category: 'beer',
  archetype: 'standard', entry_year: i === 7 ? 2 : 1, exit_year: i === 6 ? 1 : null,
  yearly: [1, 2, 3].map(year => ({year, profit: i * 10 + year, market_share: i / 100}))
}]));
const D = {firms, meta: {years: 3}, events: [{firm: 'f6', year: 1, event: 'bankruptcy'}], brands: [
  {brand: 'b', name: 'Brand', category: 'beer', owner: 'f0', year: 2, positioning: 'standard', traits: ['lager']},
  {brand: 'b', name: 'Brand', category: 'beer', owner: 'f1', year: 3, positioning: 'standard', traits: ['lager']}
]};
let lastChart;
const S = {cmp: []};
$('#cp-category').value='all';$('#cp-product').value='all';$('#cp-status').value='all';
const context = {
  $, $$: () => [], D, S, years: [1, 2, 3], range: {from: 1, to: 3},
  STAGES: ['retailer'], STAGE: {retailer: 'Retail'}, CAT: {beer: 'Bier'}, ARCH: {standard: 'Standard'},
  EVENT: {bankruptcy: 'Konkurs'}, store: {get: (_, fallback) => fallback, set: () => {}},
  bankActors:()=>({}),FM_GROUPS:['retailer'],fmGroup:f=>f.stage,fmGroupLabel:String,
  navigateView:change=>change(),sumBy:(a,k)=>a.reduce((n,r)=>n+(r[k]||0),0),
  pal: () => ['red', 'blue', 'green', 'orange', 'purple', 'cyan'], stageColor: () => ({retailer: 'red'}),
  firm: id => firms[id], fname: id => firms[id]?.name || id, actorLabel: id => String(firms[id]?.name || id).replaceAll('<', '&lt;').replaceAll('>', '&gt;'), firmProfit: id => firms[id].yearly[2].profit,
  inRange: year => year >= 1 && year <= 3, empty: text => text,
  esc: value => String(value ?? '').replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
  chf: String, pct: String, nf: String, kpi: text => text,
  destroy: () => {}, fmtAxis: () => ({}), chart: (_, cfg) => { lastChart = cfg; }, wireFirmLinks: () => {}
};
vm.createContext(context);
vm.runInContext(source.slice(start, end), context);
vm.runInContext('renderCompare()', context);
assert.match($('#cp-charts').innerHTML, /Top 5/);
S.cmp = Object.keys(firms);
vm.runInContext('renderCompare()', context);
assert.equal(S.cmp.length, 6);
assert.equal(($('#cp-firms').innerHTML.match(/disabled/g) || []).length, 2);
assert.equal(lastChart.data.datasets.length, 6);
const colors = lastChart.data.datasets.map(d => d.borderColor);
assert.equal(new Set(colors).size, 6);
S.cmp = ['f0', 'f2'];
vm.runInContext('renderCompare()', context);
assert.equal(lastChart.data.datasets[1].borderColor, colors[2]);
S.cmpRelative = true;
vm.runInContext('renderCompare()', context);
// Year 1 excludes the entrant; years 2/3 exclude the firm that left in year 1.
assert.equal(lastChart.data.datasets[0].data[0], 1 - 31);
assert.equal(lastChart.data.datasets[0].data[1], 2 - (2 + 12 + 22 + 32 + 42 + 52 + 72) / 7);
assert.match($('#cp-summary').innerHTML, /class="num best"/);
S.cmp = ['f6', 'f7'];
S.cmpRelative = false;
vm.runInContext('renderCompare()', context);
assert.equal(lastChart.data.datasets[0].data[1], null);
assert.equal(lastChart.data.datasets[1].data[0], null);
$('#cp-clear').onclick();
assert.equal(S.cmp.length, 0);
$('#cp-top').onclick();
assert.equal(S.cmp.length, 5);
vm.runInContext('renderStructure()', context);
assert.match($('#ms-timeline').innerHTML, /<svg/);
assert.match($('#ms-timeline').innerHTML, /Firm &lt;0&gt;/);
assert.match($('#ms-timeline').innerHTML, /Konkurs/);
assert.match($('#ms-brands').innerHTML, /seit Jahr 2/);
assert.match($('#ms-brands').innerHTML, /Firm &lt;1&gt;/);
$('#cp-status').value='exited';
vm.runInContext('renderCompare()',context);
assert.match($('#cp-count').textContent,/1 Treffer/);
assert.match($('#cp-firms').innerHTML,/Jahr 1/);
$('#cp-status').value='all';$('#cp-years').value='3';
vm.runInContext('renderCompare()',context);
assert.match($('#cp-count').textContent,/6 Treffer/);
$('#cp-years').value='0';$('#cp-category').value='factory';$('#cp-product').value='wine';
firms.f0.stage='factory';firms.f0.category='wine';context.FM_GROUPS.push('factory','bank');
vm.runInContext('renderCompare()',context);assert.match($('#cp-count').textContent,/1 Treffer/);
context.bankActors=()=>({'bank:B1':{id:'bank:B1',name:'Bank',stage:'bank',entry_year:1,exit_year:null,
 yearly:[1,2,3].map(year=>({year,profit:5,revenue:20,equity:75,deposit_share:0.4}))}});
$('#cp-category').value='bank';S.cmp=['bank:B1'];S.cmpMetric='cash';
vm.runInContext('renderCompare()',context);
assert.deepEqual(Array.from(lastChart.data.datasets[0].data),[75,75,75]);
assert.doesNotMatch($('#cp-metrics').innerHTML,/Lieferquote|Reputation/);
console.log('Comparison selection, colors, relative values, statistics and structure passed.');
