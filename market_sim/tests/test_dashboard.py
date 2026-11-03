from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

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
        entry = [e["year"] for e in data["events"] if e["firm"] == firm["id"] and e["event"] in ("market_entry", "spin_off")]
        assert firm["entry_year"] == min(entry, default=1)
        assert len(firm["yearly"]) == 2
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
    for tab in ("overview", "market", "map", "people", "firms", "compare", "structure", "chain", "finance", "state", "rnd", "events"):
        assert f'data-tab="{tab}"' in content
        assert f'id="tab-{tab}"' in content
    assert 'id="cp-relative"' in content
    assert 'id="cp-search"' in content
    assert 'id="cp-add"' not in content
    assert 'id="fi-negative"' in content
    assert "Hat es sich gelohnt?" in content


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional for Python-only installations")
def test_comparison_and_structure_javascript():
    directory = Path(__file__).parent
    subprocess.run(["node", str(directory / "dashboard_phase8_check.cjs"),
                    str(directory.parent / "dashboard.py")], check=True, capture_output=True, text=True)
