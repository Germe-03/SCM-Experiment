"""Phase 30: Post und Kuriere im Dashboard."""

from __future__ import annotations

import shutil
import subprocess

import pytest

from market_sim.config import load_market_config
from market_sim.dashboard import write_dashboard_html
from market_sim.dashboard_data import build_dashboard_data
from market_sim.run import build_runner


def test_dashboard_has_transport_tab_and_carrier_data(tmp_path):
    config = load_market_config()
    carriers = config.carriers.model_copy(update={
        "enabled": True,
        "couriers": config.carriers.couriers.model_copy(update={
            "enabled": True,
            "entry_probability": 1.0,
        }),
    })
    config = config.model_copy(update={"carriers": carriers})

    runner, years = build_runner(2, 0, days_per_year=30, config=config)
    result = runner.run(years)
    data = build_dashboard_data(result, runner.network, config, 0)

    assert data["carriers"] == result.carriers
    assert data["carriers"]

    path = write_dashboard_html(data, tmp_path / "d.html")
    html = path.read_text(encoding="utf-8")
    assert 'id="tab-couriers"' in html
    assert 'data-tab="couriers"' in html
    assert "function renderCouriers" in html
    assert "id=\"trucks-box\"" in html
    assert "__TRUCKS__" not in html
    assert "__CARRIERS__" not in html


def test_render_transport_runs_in_node(tmp_path):
    if shutil.which("node") is None:
        pytest.skip("Node is optional for Python-only installations")

    script = tmp_path / "check_transport.cjs"
    script.write_text(
        r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const elements = new Map();
const charts = new Map();
const context = {
  D: {
    regions: [
      {name: 'zuerich', population_share: 0.2, x: 683, y: 248},
      {name: 'tessin', population_share: 0.05, x: 717, y: 96}
    ],
    carriers: [
      {
        year: 1, carrier: 'post', kind: 'post', name: 'Die Post', regions: '',
        units: 100, revenue: 1000, profit: -100, bundesbeitrag: 100,
        mean_delay_days: 1, next_tariff: 1.4,
        share_own: 0.2, share_post: 0.6, share_couriers: 0.2, tariff: 1.3
      },
      {
        year: 2, carrier: 'post', kind: 'post', name: 'Die Post', regions: '',
        units: 120, revenue: 1200, profit: -120, bundesbeitrag: 120,
        mean_delay_days: 2, next_tariff: 1.5,
        share_own: 0.2, share_post: 0.6, share_couriers: 0.2, tariff: 1.4
      },
      {
        year: 2, carrier: 'courier_01', kind: 'courier',
        name: 'Schneller Kurier', regions: 'zuerich',
        units: 20, revenue: 300, profit: 50, bundesbeitrag: 0,
        mean_delay_days: 0.5, next_tariff: 0,
        share_own: 0, share_post: 0, share_couriers: 0, tariff: 0
      }
    ]
  },
  $: selector => {
    if (!elements.has(selector)) elements.set(selector, {innerHTML: ''});
    return elements.get(selector);
  },
  $$: () => [],
  chart: (id, config) => charts.set(id, config),
  esc: String,
  nf: (value, digits) => String(value),
  pct: value => String(value),
  chf: value => String(value),
  pal: () => ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'],
  empty: text => text,
  kpi: (label, value) => `<div>${label}${value}</div>`,
  REGION: {zuerich: 'Zürich', tessin: 'Tessin'}
};

vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
vm.runInContext('renderTransport()', context);

for (const id of ['tr-shares', 'tr-post', 'tr-delay']) {
  assert.ok(charts.has(id), `missing chart ${id}`);
}
assert.ok(elements.get('#tr-map').innerHTML.includes('circle'));
assert.ok(elements.get('#tr-table').innerHTML.includes('Schneller Kurier'));

context.D.carriers = [];
vm.runInContext('renderTransport()', context);
assert.ok(elements.get('#tr-kpis').innerHTML.includes('ausgeschaltet'));
""",
        encoding="utf-8",
    )

    js_path = __import__("pathlib").Path(__file__).parents[1] / "dashboard_carriers.js"
    subprocess.run(["node", str(script), str(js_path)], check=True)
