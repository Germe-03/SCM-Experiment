// Phase 22: share price in the compare tab, index switch off there and on in the stock tab.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const saved = new Map(), charts = new Map();
const el = () => ({innerHTML: '', onchange: null, querySelector(sel) {return this.kids[sel] ??= el()}, kids: {}});
const context = {
  D: {stocks: {days: [1, 2, 3, 4], years: [1, 1, 2, 2], index: [100, 110, 120, 0], prices: {a: [null, 10, 12, 8], b: [5, 0, null, null]}}},
  store: {get: (k, d) => saved.has(k) ? saved.get(k) : d, set: (k, v) => saved.set(k, v)},
  stockPoints: () => [0, 1, 2, 3], stockLabel: i => 'P' + i,
  stockNormal: (vs, base) => {base = base ?? vs.find(v => v != null && v > 0); return vs.map(v => v == null || !base ? null : 100 * v / base)},
  stockDataset: (label, data, borderColor, borderWidth = 2) => ({label, data, borderColor, borderWidth}),
  stockOptions: () => ({scales: {x: {}, y: {title: {}}}}), chart: (id, cfg) => charts.set(id, cfg), fmtAxis: () => ({}),
  nf: String, pct: v => v == null ? '—' : Math.round(v * 100) + '%', esc: String, pal: () => ['c0', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'grey'],
  renderCompare: () => {}};
vm.createContext(context);
vm.runInContext(source, context);
const run = code => vm.runInContext(code, context);
assert.equal(run('hasStockPrices("a")'), true);
assert.equal(run('hasStockPrices("b")'), true);
assert.equal(run('hasStockPrices("c")'), false);
assert.equal(run('stockIndexShown("sx", true)'), true, 'index shown by default in the stock tab');
assert.equal(run('stockIndexShown("cmp", false)'), false, 'index hidden by default in compare');
const stats = run('stockStats("a",[0,1,2,3])');
assert.deepEqual([stats.last, stats.high, stats.highYear, stats.low, stats.lowYear], [8, 12, 2, 8, 2]);
assert.ok(Math.abs(stats.change + 0.2) < 1e-9);
context.root = el();
run('renderCompareStock(root,["a","c"],id=>id.toUpperCase(),id=>"red")');
let cfg = charts.get('cp-metric');
assert.equal(cfg.data.datasets.length, 1, 'no index line by default');
assert.deepEqual(cfg.data.datasets[0].data, [null, 100, 120, 80]);
assert.match(context.root.innerHTML, /C ist im gewählten Zeitraum nicht an der Börse/);
assert.match(context.root.innerHTML, /Börsenindex einblenden/);
assert.match(context.root.kids['#cp-summary'].innerHTML, /nicht an der Börse/);
saved.set('stock-index-cmp', true); saved.set('cmp-stock-norm', false);
run('renderCompareStock(root,["a"],id=>id,id=>"red")');
cfg = charts.get('cp-metric');
assert.equal(cfg.data.datasets.length, 2);
assert.equal(cfg.data.datasets[1].label, 'Börsenindex');
assert.equal(cfg.data.datasets[1].yAxisID, 'y2');
assert.deepEqual(cfg.data.datasets[0].data, [null, 10, 12, 8]);
assert.ok(cfg.options.scales.y2);
console.log('ok');
