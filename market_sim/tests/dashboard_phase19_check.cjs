// Parse a rendered dashboard and exercise finance charts with a small DOM stub.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[2], 'utf8');
const D = JSON.parse(html.match(/<script id="dashboard-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
scripts.forEach(s => new vm.Script(s));
const source = scripts[0], nodes = new Map(), charts = new Map();
const $ = id => {if (!nodes.has(id)) nodes.set(id, {}); return nodes.get(id)};
const range = {from: 1, to: 2}, S = {};
const context = {D, S, range, $, $$: () => [],
  inRange: y => y >= range.from && y <= range.to,
  sys: () => D.system.filter(x => x.year >= range.from && x.year <= range.to),
  firm: id => D.firms[id], fname: id => D.firms[id]?.name || id,
  esc: v => String(v ?? '').replaceAll('<', '&lt;'),
  nf: String, chf: String, pct: String, empty: String, fmtAxis: () => ({}),
  pal: () => ['red','blue','green','orange','purple','cyan','pink','black'],
  chart: (id, cfg) => charts.set(id, cfg), lines: (id, series) => charts.set(id, series),
  render: () => vm.runInContext('renderStocks()', context)};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function renderBanks()'), source.indexOf('function renderFinance()')), context);
vm.runInContext('renderBanks();renderStocks()', context);
assert.match($('#fi-banks').innerHTML, /Eigenkapitalquote/);
assert.equal(charts.get('fi-stocks').data.labels.length, 6);
const ids = Object.keys(D.stocks.prices).slice(0, 2);
S.stockFirms = ids;
$('#fi-stock-period').onchange({target: {value: 'month'}});
assert.equal(charts.get('fi-stocks').data.labels.length, 2);
assert.equal(charts.get('fi-stocks').data.datasets.length, 3);
range.from = 2;
vm.runInContext('renderBanks();renderStocks()', context);
assert.equal($('#fi-bank-year').textContent, 'Stand: Jahr 2');
assert.ok(charts.get('fi-stocks').data.labels.every(s => s.startsWith('Jahr 2')));
vm.runInContext(`renderStockChart('fd-price', [${JSON.stringify(ids[0])}], false, 'week', 'fd-stock-empty')`, context);
assert.equal(charts.get('fd-price').data.datasets.length, 1);
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
D.stocks = {days: [], years: [], index: [], prices: {}}; D.banks = [];
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
console.log('Phase 19 syntax, finance charts, filters, listing gaps and bank flows passed.');
