// Run dashboard_holdings.js against small stubs and check the generated holdings html.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2], 'utf8');
const boxes = {};
const D = {
  firms: {a: {name: 'Alpha AG'}, b: {name: 'Beta AG'}},
  holding_groups: [{holding: 'holding_a', name: 'Alpha AG Holding', listing_id: 'a', status: 'active', founded_year: 2,
    dissolved_year: null, successor: null, cash: 5e6,
    subs: [{firm: 'a', name: 'Alpha AG', active: true, cash: 1e6, reserve: 2e6, reserve_floor: 1e6, revenue: 1e7, profit: 1e5},
           {firm: 'b', name: 'Beta AG', active: true, cash: 1e6, reserve: 2e6, reserve_floor: 1e6, revenue: 8e6, profit: -1e5}]}],
  holding_log: [{holding: 'holding_a', year: 2, details: 'Alpha AG Holding gegründet'}],
};
const views = {firms: () => {}, compare: () => {}, stocks: () => {}};
const context = {D, S: {}, VIEWS: views, EVENT: {}, range: {from: 1, to: 5}, inRange: y => y >= 1 && y <= 5,
  $: id => { boxes[id] = boxes[id] || {querySelectorAll: () => [], innerHTML: ''}; return boxes[id]; },
  esc: v => String(v ?? ''), nf: String, pct: String, chf: v => String(v), fname: id => D.firms[id]?.name || id,
  firm: id => D.firms[id], wireFirmLinks() {}, store: {set() {}}, renderCompare() {}, addStock() {},
  hasStockPrices: () => true, empty: m => '<div>' + m + '</div>'};
vm.createContext(context);
vm.runInContext(source, context);
for (const tab of ['firms', 'compare', 'stocks']) views[tab]();
assert.match(boxes['#hg-firms'].innerHTML, /Alpha AG Holding/);
assert.match(boxes['#hg-firms'].innerHTML, /Beta AG/);
assert.match(boxes['#hg-compare'].innerHTML, /data-hg-cmp/);
assert.match(boxes['#hg-stocks'].innerHTML, /data-hg-stock/);
assert.equal(context.EVENT.holding_formed, 'Holding gegründet');
D.holding_groups = [];
views.firms();
assert.match(boxes['#hg-firms'].innerHTML, /keine Holding/);
