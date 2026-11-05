// Phase 27: research trees, patent table, firm detail compensation and finance split.
// Usage: node dashboard_phase27_check.cjs <dashboard_rnd.js> [dashboard.html]
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const nodes = new Map(), charts = new Map(), saved = new Map();
const $ = sel => {if (!nodes.has(sel)) nodes.set(sel, {innerHTML: '', onclick: null, querySelectorAll: () => []}); return nodes.get(sel)};
const range = {from: 1, to: 10}, S = {};
const D = {
  meta: {years: 10},
  rnd_trees: {
    factory: [
      {name: 'prozessautomation', label: 'Prozessautomation', requires: [], complexity: 'simple', patentable: false, branch: 'automation', categories: []},
      {name: 'robotik', label: 'Robotik', requires: ['prozessautomation'], complexity: 'medium', patentable: false, branch: 'automation', categories: []},
      {name: 'prognose_software', label: 'Prognose-Software', requires: [], complexity: 'simple', patentable: false, branch: 'automation', categories: []},
      {name: 'smart_factory', label: 'Smart Factory', requires: ['robotik', 'prognose_software'], complexity: 'complex', patentable: true, branch: 'automation', categories: []}],
    distributor: [
      {name: 'routenplanung', label: 'Routenplanung', requires: [], complexity: 'simple', patentable: false, branch: 'logistik', categories: []},
      {name: 'kuehlkette', label: 'Kühlkette', requires: ['routenplanung'], complexity: 'medium', patentable: true, branch: 'logistik', categories: []}]},
  rnd: [
    {firm: 'f1', project: 'prozessautomation', tree: 'factory', step: 'research', start_year: 1, end_year: 2, cost: 60, success: true, result: 'erforscht'},
    {firm: 'f1', project: 'prozessautomation', tree: 'factory', step: 'implementation', start_year: 3, end_year: 3, cost: 30, success: true, result: 'Produktivität'},
    {firm: 'f2', project: 'prozessautomation', tree: 'factory', step: 'research', start_year: 2, end_year: 3, cost: 20, success: true, result: 'erforscht'},
    {firm: 'f2', project: 'robotik', tree: 'factory', step: 'research', start_year: 4, end_year: 5, cost: 80, success: false, result: 'kein Ergebnis'},
    {firm: 'f1', project: 'smart_factory', tree: 'factory', step: 'research', start_year: 6, end_year: 8, cost: 150, success: true, result: 'erforscht'},
    // Old runs: no tree and no step.
    {firm: 'f3', project: 'routenplanung', start_year: 1, end_year: 1, cost: 10, success: true, result: 'Transport -15%'}],
  patents: [
    {tree: 'factory', stage: 'smart_factory', holder: 'f1', first_holder: 'f1', granted_year: 8, years: 5, expires_year: 13, fee: 7e6, prior_users: [], status: 'active', end_year: null},
    {tree: 'distributor', stage: 'kuehlkette', holder: 'f3', first_holder: 'f3', granted_year: 2, years: 3, expires_year: 5, fee: 5e6, prior_users: [], status: 'expired', end_year: 5}],
  firms: {
    f1: {id: 'f1', name: 'Alpha <AG>', stage: 'factory', channel: null, yearly: [
      {year: 8, rnd_cost: 100, cash_flows: {'schadenersatz:f2': 40e6, 'staat:Patentgebühr': -7e6}},
      {year: 9, rnd_cost: 0, cash_flows: {'schadenersatz:f2': 10e6}}]},
    f2: {id: 'f2', name: 'Beta', stage: 'factory', channel: null, yearly: [
      {year: 8, rnd_cost: 0, cash_flows: {'schadenersatz:f1': -40e6, 'staat:Busse patentverletzung': -5e6}},
      {year: 9, cash_flows: {'schadenersatz:f1': -10e6}}]},
    f3: {id: 'f3', name: 'Gamma', stage: 'distributor', channel: null, yearly: [{year: 2, cash_flows: {'staat:Patentgebühr': -5e6}}]}},
  system: Array.from({length: 10}, (_, i) => ({year: i + 1, rnd_project_spend: 0})),
  offence_ledger: [
    {firm: 'f2', offence: 'patentverletzung', year: 8, gain: 30e6, fine: 5e6, damage: 2e6, net: -17e6, paid_off: false, compensation: 40e6, holder: 'f1'},
    {firm: 'f3', offence: 'lohndumping', year: 4, gain: 1e6, fine: 0, damage: 0, net: 1e6, paid_off: true}]};
const esc = v => String(v ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const context = {D, S, range, $, $$: () => [], store: {get: (k, d) => saved.has(k) ? saved.get(k) : d, set: (k, v) => saved.set(k, v)},
  inRange: y => y >= range.from && y <= range.to, sys: () => D.system.filter(x => x.year >= range.from && x.year <= range.to),
  firm: id => D.firms[id], fname: id => D.firms[id]?.name || id, actorLabel: id => esc(D.firms[id]?.name || id),
  esc, chf: v => 'CHF' + Math.round(v ?? 0), nf: String, pct: v => Math.round(v * 100) + '%',
  kpi: (label, value, note = '') => `<div class="kpi">${label}: ${value} ${note}</div>`, empty: msg => `<div class="empty">${esc(msg)}</div>`,
  wireFirmLinks: () => {}, chart: (id, cfg) => charts.set(id, cfg), fmtAxis: () => ({}), css: n => '#' + n.replace(/\W/g, ''),
  pal: () => ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8'], OFFENCE: {lohndumping: 'Lohndumping', patentverletzung: 'Patentverletzung'}};
vm.createContext(context);
vm.runInContext(source, context);
vm.runInContext(source, context); // the dashboard checks load files twice: only function declarations allowed
const run = code => vm.runInContext(code, context);

// Labels and steps.
assert.equal(run("rndLabel('factory','smart_factory')"), 'Smart Factory');
assert.equal(run("rndLabel('factory','unbekannt')"), 'unbekannt');
assert.equal(run("rndStep({step:'implementation'})"), 'Umsetzung');
assert.equal(run("rndStep({step:'research'})"), 'Forschung');
assert.equal(run("rndStep({})"), 'Forschung');

// Progress up to the end of the selected range.
let p = run("rndProgress('factory')");
assert.equal(p.prozessautomation.researched, 1, 'f2 researched only');
assert.equal(p.prozessautomation.implemented, 1, 'f1 implemented');
assert.equal(p.robotik.researched + p.robotik.implemented, 0, 'failure counts nothing');
assert.equal(p.smart_factory.researched, 1);
assert.equal(p.prozessautomation.firms.f1, 'implemented');
assert.equal(p.prozessautomation.firms.f2, 'researched');
range.to = 2;
p = run("rndProgress('factory')");
assert.equal(p.prozessautomation.researched, 1);
assert.equal(p.prozessautomation.implemented, 0);
assert.equal(p.smart_factory.researched, 0);
range.to = 10;
assert.equal(run("rndProgress('distributor')").routenplanung.researched, 1, 'old rows without tree found by project name');

// Patent state at a year.
assert.equal(run("rndPatent('factory','smart_factory',7)"), null);
let pat = run("rndPatent('factory','smart_factory',10)");
assert.equal(pat.active, true); assert.equal(pat.holder, 'f1'); assert.equal(pat.expires_year, 13);
assert.equal(run("rndPatent('distributor','kuehlkette',4)").active, true);
assert.equal(run("rndPatent('distributor','kuehlkette',5)").active, false);

// Tree graphic for the whole sector.
let svg = run("rndTreeSvg('factory')");
assert.match(svg, /<svg/);
assert.equal((svg.match(/data-stage="/g) || []).length, 4, 'one node per stage');
assert.match(svg, /data-stage="smart_factory"/);
assert.match(svg, /Smart Factory/);
assert.match(svg, /Alpha &lt;AG&gt;/, 'patent holder name escaped');
assert.match(svg, /bis Jahr 13/);
assert.match(svg, /gesperrt/);
assert.equal((svg.match(/data-edge="/g) || []).length, 3, 'one arrow per requirement');
assert.match(svg, /data-edge="robotik>smart_factory"/);
assert.match(svg, /umgesetzt 1/);
assert.match(svg, /erforscht 1/);
// Small tree for one firm.
svg = run("rndTreeSvg('factory','f2')");
assert.match(svg, /data-state="researched"[^>]*data-stage="prozessautomation"|data-stage="prozessautomation"[^>]*data-state="researched"/);
assert.match(svg, /gesperrt/, 'f2 is blocked by the patent of f1');
svg = run("rndTreeSvg('factory','f1')");
assert.match(svg, /data-stage="prozessautomation"[^>]*data-state="implemented"|data-state="implemented"[^>]*data-stage="prozessautomation"/);
assert.doesNotMatch(svg, /gesperrt/, 'own patent does not block');
assert.equal(run("rndTreeSvg('nichts')"), '');

// Tree tab with chips.
run('renderRndTrees()');
assert.match($('#rd-tree-chips').innerHTML, /data-tree="factory"/);
assert.match($('#rd-tree-chips').innerHTML, /Hersteller/);
assert.match($('#rd-tree-chips').innerHTML, /Verteilung/);
assert.doesNotMatch($('#rd-tree-chips').innerHTML, /Gastronomie/, 'only trees in the data');
assert.match($('#rd-tree').innerHTML, /data-stage="smart_factory"/);
$('#rd-tree-chips').onclick({target: {closest: () => ({dataset: {tree: 'distributor'}})}});
assert.equal(S.rdTree, 'distributor');
assert.match($('#rd-tree').innerHTML, /data-stage="kuehlkette"/);
assert.match($('#rd-tree').innerHTML, /abgelaufen/);

// Patent table.
run('renderPatentTable()');
let t = $('#rd-patents').innerHTML;
for (const head of ['Stufe', 'Inhaber', 'erteilt', 'Ablauf', 'Laufzeit', 'Gebühr', 'Status']) assert.match(t, new RegExp('<th[^>]*>' + head));
assert.match(t, /Smart Factory/); assert.match(t, /Kühlkette/);
assert.match(t, /data-firm="f1"/);
assert.match(t, /aktiv/); assert.match(t, /abgelaufen/);
range.to = 4;
run('renderPatentTable()');
t = $('#rd-patents').innerHTML;
assert.doesNotMatch(t, /Smart Factory/, 'granted after the range');
assert.match(t, /Kühlkette/); assert.match(t, />aktiv</, 'still active in year 4');
range.to = 1;
run('renderPatentTable()');
assert.match($('#rd-patents').innerHTML, /class="empty"/);
range.to = 10;

// Firm detail: damages and own progress.
assert.deepEqual({...run("firmDamages('f1')")}, {paid: 0, received: 50e6});
assert.deepEqual({...run("firmDamages('f2')")}, {paid: 50e6, received: 0});
range.from = 9;
assert.deepEqual({...run("firmDamages('f2')")}, {paid: 10e6, received: 0});
range.from = 1;
let html = run("firmRndHtml('f2')");
assert.match(html, /Schadenersatz bezahlt/); assert.match(html, /CHF50000000/);
assert.match(html, /<svg/);
html = run("firmRndHtml('f1')");
assert.match(html, /Schadenersatz erhalten/); assert.match(html, /Smart Factory/, 'own patents listed');
assert.match(run("firmRndHtml('f3')"), /Kühlkette/);

// Split of research and implementation spend.
let sp = run("rndSplit(D.rnd.filter(x=>x.firm==='f1'),3,90)");
assert.equal(sp.research, 0); assert.equal(sp.implementation, 90);
sp = run("rndSplit(D.rnd.filter(x=>x.firm==='f1'),1,30)");
assert.equal(sp.research, 30); assert.equal(sp.implementation, 0);
sp = run("rndSplit([{step:'research',start_year:1,end_year:3,cost:30},{step:'implementation',start_year:3,end_year:3,cost:10}],3,20)");
assert.equal(sp.research, 10, 'research cost spread over all years'); assert.equal(sp.implementation, 10);
sp = run("rndSplit([],5,12)");
assert.equal(sp.research, 12); assert.equal(sp.implementation, 0, 'unknown split counts as research');
sp = run("rndSplit(D.rnd,3,100)");
assert.ok(Math.abs(sp.research + sp.implementation - 100) < 1e-9);

// Finance chart: four series.
D.system.forEach(x => x.rnd_project_spend = 100);
run("renderRndMoney('fi-rnd')");
const cfg = charts.get('fi-rnd');
assert.deepEqual(Array.from(cfg.data.datasets, d => d.label), ['Forschung', 'Umsetzung', 'Patentgebühren', 'Schadenersatz']);
assert.equal(cfg.data.labels.length, 10);
assert.equal(cfg.data.datasets[2].data[1], 5e6, 'patent fee of year 2');
assert.equal(cfg.data.datasets[2].data[7], 7e6);
assert.equal(cfg.data.datasets[3].data[7], 40e6, 'only paid damages count');

// State tab: patent infringements with compensation.
run('renderPatentOffences()');
t = $('#st-patents').innerHTML;
assert.match(t, /Schadenersatz/); assert.match(t, /CHF40000000/); assert.match(t, /Alpha &lt;AG&gt;/);
assert.doesNotMatch(t, /Lohndumping/);
D.offence_ledger = [];
run('renderPatentOffences()');
assert.match($('#st-patents').innerHTML, /class="empty"/);

// No tree data at all (trees off or old runs).
D.rnd_trees = {}; D.patents = undefined;
run('renderRndTrees()');
assert.match($('#rd-tree').innerHTML, /class="empty"/);
run('renderPatentTable()');
assert.match($('#rd-patents').innerHTML, /class="empty"/);
assert.equal(typeof run("firmRndHtml('f1')"), 'string');

// Optional: a rendered dashboard keeps its scripts parseable and exports the trees.
if (process.argv[3]) {
  const page = fs.readFileSync(process.argv[3], 'utf8');
  [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].forEach(m => new vm.Script(m[1]));
  assert.ok(!page.includes('__RND__'));
  const data = JSON.parse(page.match(/<script id="dashboard-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  assert.ok(data.rnd_trees && typeof data.rnd_trees === 'object');
}
console.log('Phase 27 checks passed.');
