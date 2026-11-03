from __future__ import annotations

import json

from market_sim.config import load_market_config
from market_sim.dashboard import CHART_JS_URL, write_dashboard_html
from market_sim.dashboard_data import build_dashboard_data
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
    assert {"meta", "firms", "system", "ranking"} <= data.keys()
    assert len(data["ranking"]) == len(data["firms"])
    for firm in data["firms"].values():
        assert len(firm["yearly"]) == 2
        assert firm["daily"]
        assert all(firm["daily"][key] for key in ("inventory", "backlog", "cash"))


def test_write_dashboard_html(tmp_path):
    path = write_dashboard_html(_data(), tmp_path / "dashboard.html")
    content = path.read_text(encoding="utf-8")
    assert path.exists() and path.stat().st_size > 0
    assert "retailer_01" in content
    assert "Aare Markt AG" in content
    assert CHART_JS_URL in content
    assert 'id="actor-selector"' in content
    assert "Alle" in content and "Keine" in content
