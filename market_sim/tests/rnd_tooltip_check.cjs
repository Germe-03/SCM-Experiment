// Usage: node rnd_tooltip_check.cjs <dashboard_rnd.js>
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const st = (name, branch, categories, requires = [], extra = {}) => ({name, label: name.toUpperCase(), requires, branch, categories, complexity: 'simple',
  patentable: false, kind: 'productivity', component: null, adds_category: null, effect: 0.1, cost: 1e6, duration_days: 100, success_probability: 0.8,
  implementation_cost: 2e5, implementation_days: 50, ...extra});
const D = {rnd_trees: {factory: [
  st('a1', 'automation', []), st('a2', 'automation', [], ['a1'], {kind: 'component_reduction', component: 'malt', effect: 0.08}),
  st('s1', 'automation', ['softdrinks']), st('s2', 'automation', ['softdrinks', 'water'], ['a1']),
  st('w1', 'automation', ['water'], [], {kind: 'maturation', effect: 0.25, patentable: true}),
  st('m1', 'marke', ['softdrinks'], [], {kind: 'new_category', adds_category: 'softdrinks'})]}, rnd: [], patents: [], firms: {}};
const range = {from: 1, to: 10}, S = {};
const esc = v => String(v ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const context = {D, S, range, esc, chf: v => 'CHF' + Math.round(v ?? 0), fname: id => id};
vm.createContext(context); vm.runInContext(source, context);
const run = c => vm.runInContext(c, context);
const spots = svg => [...svg.matchAll(/<g data-stage="([^"]+)"[^>]*><rect x="(\d+)" y="(\d+)"/g)].map(m => [m[1], m[2] + ',' + m[3]]);
for (const cat of [null, 'softdrinks', 'water', 'beer']) {
  const list = spots(run(`rndTreeSvg('factory', null, ${JSON.stringify(cat)})`));
  assert.ok(list.length > 0);
  assert.equal(new Set(list.map(x => x[1])).size, list.length, 'overlapping nodes for ' + cat);
}
assert.equal(spots(run("rndTreeSvg('factory', null, 'beer')")).length, 2, 'beer: only general stages');
assert.equal(spots(run("rndTreeSvg('factory', null, 'softdrinks')")).length, 5);
assert.match(run("rndTooltipHtml('factory','a2')"), /Malzkosten −8 %/);
assert.match(run("rndTooltipHtml('factory','w1')"), /Reifezeit −25 %[\s\S]*Patentierbar: ja/);
assert.match(run("rndTooltipHtml('factory','a2')"), /Voraussetzungen: A1/);
assert.match(run("rndTooltipHtml('factory','m1')"), /Neue Marke \(Softdrinks\)/);
console.log('ok');
