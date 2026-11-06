// Phase 21: amounts from 1'000 Mio. CHF are shown as Mia. CHF in the dashboard.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const src = fs.readFileSync(process.argv[2], 'utf8');
const line = name => src.split('\n').find(l => l.startsWith(`const ${name}=`));
const context = {D: {firms: {}}, bankActors: () => ({}), courierActors: () => ({}), REGION: {}, Intl};
vm.createContext(context);
for (const name of ['nf', 'mia', 'chf', 'pretty']) vm.runInContext(line(name).replace(/^const /, 'var '), context);
const run = code => vm.runInContext(code, context);
assert.equal(run(`pretty("Verlust von 2'652 Mio. CHF")`), 'Verlust von 2,65 Mia. CHF');
assert.equal(run(`pretty("Gewinn -1'200 Mio. CHF")`), 'Gewinn -1,20 Mia. CHF');
assert.equal(run(`pretty("Gewinn 52 Mio. CHF")`), 'Gewinn 52 Mio. CHF');
assert.equal(run(`pretty("Gewinn 999 Mio. CHF")`), 'Gewinn 999 Mio. CHF');
assert.equal(run('chf(2652000000)'), '2,65 Mia. CHF');
assert.equal(run('chf(-3100000000)'), '-3,10 Mia. CHF');
assert.match(run('chf(52000000)'), / Mio\. CHF$/);
console.log('ok');
