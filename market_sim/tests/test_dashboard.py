from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from market_sim.config import load_market_config
from market_sim.dashboard import CHART_JS_URL, write_dashboard_html
from market_sim.dashboard_data import _stock_weekly, build_dashboard_data
from market_sim.models import load_firms
from market_sim.run import run_simulation


def _data():
    config = load_market_config()
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={"years": 2, "days_per_year": 15})
    })
    network = load_firms()
    result = run_simulation(2, 0, 15, config, network)
    return build_dashboard_data(result, network, config, 0)


def test_dashboard_data_is_complete_and_json_serializable():
    data = _data()
    json.dumps(data)
    assert {"meta", "firms", "system", "ranking", "banks", "stocks"} <= data.keys()
    assert len(data["ranking"]) == len(data["firms"])
    for firm in data["firms"].values():
        entry = [e["year"] for e in data["events"] if e["firm"] == firm["id"] and e["event"] in ("market_entry", "spin_off")]
        assert firm["entry_year"] == min(entry, default=1)
        assert len(firm["yearly"]) == 2
        assert all("paid_items" in row and "sold_items" in row for row in firm["yearly"])
        assert all(0 <= row["service_level"] <= 1 for row in firm["yearly"])
        # Weekly means keep 50-year runs small enough for one HTML file.
        assert all(firm["weekly"][key] for key in ("inventory", "backlog", "cash"))


def test_write_dashboard_html(tmp_path):
    path = write_dashboard_html(_data(), tmp_path / "dashboard.html")
    content = path.read_text(encoding="utf-8")
    assert path.exists() and path.stat().st_size > 0
    assert "retailer_01" in content
    assert "Aare Markt AG" in content
    assert CHART_JS_URL in content
    assert 'id="actor-selector"' in content
    for tab in ("overview", "market", "map", "firms", "compare", "chain", "finance", "stocks", "state", "rnd", "events", "chronicle"):
        assert f'data-tab="{tab}"' in content
        assert f'id="tab-{tab}"' in content
    assert 'data-tab="structure"' not in content
    assert 'id="tab-structure"' not in content
    assert '<dialog id="structure"' in content
    assert 'id="structure-open"' in content.split('id="tab-firms"')[1].split('</section>')[0]
    assert 'Was es zu kaufen gibt' in content.split('id="tab-market"')[1].split('id="tab-map"')[0]
    assert "setAttribute('aria-label','Filter für '+label)" in content
    assert "table.id==='ev-table'&&label==='Details'" in content
    for table in ('fm-table', 'rd-table', 'ev-table', 'fi-banks', 'sx-top', 'fi-holdings'):
        assert repr(table) in content
    assert 'data-tab="people"' not in content
    assert 'id="tab-people"' not in content
    market = content.split('id="tab-market"')[1].split('</section>')[0]
    assert "Bevölkerung" in market
    assert 'aria-label="Zurück"' in content
    for control in ("cp-category", "cp-product", "cp-status", "cp-years", "cp-count", "view-back"):
        assert f'id="{control}"' in content
    assert 'id="cp-relative"' in content
    assert 'id="cp-search"' in content
    assert 'id="cp-add"' not in content
    assert 'id="fi-negative"' in content
    for chart_id in ("fi-policy", "fi-bank-equity", "fi-bank-balances", "fi-banks", "fi-stocks"):
        assert f'id="{chart_id}"' in content
    assert "Hat es sich gelohnt?" in content
    finance = content.split('id="tab-finance"')[1].split('</section>')[0]
    stocks = content.split('id="tab-stocks"')[1].split('</section>')[0]
    assert 'fi-stock-firms' not in content
    assert 'fi-stocks' not in finance
    assert 'id="sx-search"' in stocks and '<datalist' in stocks
    assert 'id="sx-top"' in stocks and 'Top 10' in stocks
    assert "'bank'];const fmGroup" in content
    assert 'function renderBankDetail' in content
    assert 'bd-income' in content and 'bd-customer-list' in content


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional for Python-only installations")
def test_comparison_and_structure_javascript():
    directory = Path(__file__).parent
    subprocess.run(["node", str(directory / "dashboard_phase8_check.cjs"),
                    str(directory.parent / "dashboard.py")], check=True, capture_output=True, text=True)
    subprocess.run(["node", str(directory / "dashboard_navigation_check.cjs"),
                    str(directory.parent / "dashboard.py")], check=True, capture_output=True, text=True)


@pytest.mark.parametrize("length,days", [(0, []), (1, [1]), (7, [7]), (14, [7, 14]), (16, [7, 14, 16])])
def test_stock_weekly_closes(length, days):
    rows = [{"global_day": day, "year": 1 if day <= 7 else 2, "day": day,
             "index": day + 0.12345,
             **({"early": 2.3456} if day <= 7 else {"late": 4.5678})}
            for day in range(1, length + 1)]
    stocks = _stock_weekly(rows)
    assert stocks["days"] == days
    assert stocks["years"] == [1 if day <= 7 else 2 for day in days]
    assert stocks["index"] == [day + 0.12 for day in days]
    if length:
        assert stocks["prices"]["early"] == [2.3456 if day <= 7 else None for day in days]
    else:
        assert stocks == {"days": [], "years": [], "index": [], "prices": {}}
    if length > 7:
        assert stocks["prices"]["late"] == [None if day <= 7 else 4.5678 for day in days]


def test_banking_and_stock_dashboard(tmp_path):
    config = load_market_config()
    config = config.model_copy(update={
        "banking": config.banking.model_copy(update={"enabled": True}),
        "central_bank": config.central_bank.model_copy(update={"enabled": True}),
        "stock_market": config.stock_market.model_copy(update={"enabled": True, "tradable_from_year": 1}),
        "simulation": config.simulation.model_copy(update={"years": 2, "days_per_year": 21}),
    })
    network = load_firms()
    result = run_simulation(2, 0, 21, config, network)
    data = build_dashboard_data(result, network, config, 0)
    assert data["banks"] == [b.model_dump(mode="json") for b in result.bank_history]
    assert data["banks"] and data["stocks"]["prices"]
    assert all(isinstance(b['customer_ids'], list) for b in data['banks'])
    for year in (1, 2):
        active = [b for b in data['banks'] if b['year'] == year and b['active']]
        for amount, share in [('deposits', 'deposit_share'), ('loans', 'loan_share')]:
            assert sum(b[share] for b in active) == pytest.approx(1 if sum(b[amount] for b in active) else 0)
    assert set(data['firms']).isdisjoint(b['bank_id'] for b in data['banks'])
    bank = data['banks'][0]
    result.events.extend([
        {'year': 1, 'day': 1, 'firm': bank['bank_id'], 'event': 'bank_failed', 'details': 'Test'},
        {'year': 1, 'day': 1, 'firm': 'retailer_01', 'event': 'account_opened', 'details': bank['name']},
    ])
    projected = build_dashboard_data(result, network, config, 0)
    assert any(e['event'] == 'bank_failed' and e['bank_id'] == bank['bank_id'] for e in projected['bank_events'])
    assert any(e['event'] == 'account_opened' and e['firm'] == 'retailer_01' and e['bank_id'] == bank['bank_id'] for e in projected['bank_events'])
    assert data["stocks"]["days"][-1] == result.stock_daily[-1]["global_day"]
    assert len(data["stocks"]["days"]) == 6
    path = write_dashboard_html(data, tmp_path / "banking.html")
    if shutil.which("node"):
        subprocess.run(["node", str(Path(__file__).with_name("dashboard_phase19_check.cjs")), str(path)],
                       check=True, capture_output=True, text=True)


def test_stock_projection_preserves_year_end_and_small_prices():
    rows = [{'global_day': day, 'year': 1 if day <= 10 else 2,
             'index': 100, 'tiny': 0.000123} for day in range(1, 21)]
    stocks = _stock_weekly(rows)
    assert stocks['days'] == [7, 10, 14, 20]
    assert stocks['prices']['tiny'] == [0.000123] * 4


def test_disabled_banking_and_stocks():
    config = load_market_config()
    config = config.model_copy(update={
        "banking": config.banking.model_copy(update={"enabled": False}),
        "stock_market": config.stock_market.model_copy(update={"enabled": False}),
    })
    network = load_firms()
    result = run_simulation(1, 0, 2, config, network)
    data = build_dashboard_data(result, network, config, 0)
    assert data["banks"] == []
    assert data["stocks"] == {"days": [], "years": [], "index": [], "prices": {}}
