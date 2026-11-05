from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

from market_sim.config import load_market_config
from market_sim.dashboard import write_dashboard_html
from market_sim.dashboard_data import _rnd_trees, build_dashboard_data
from market_sim.models import load_firms
from market_sim.run import run_simulation
from market_sim.texts import firm_facts, year_facts
from market_sim.llm import unchecked_numbers


def _data():
    config = load_market_config()
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={"years": 2, "days_per_year": 15})
    })
    network = load_firms()
    result = run_simulation(2, 0, 15, config, network)
    return build_dashboard_data(result, network, config, 0)


@pytest.fixture(scope="module")
def dashboard_data():
    return _data()


def test_rnd_trees_export(dashboard_data):
    config = load_market_config()
    data = dashboard_data

    assert set(data["rnd_trees"]) == set(config.research.trees)
    expected_keys = {"name", "label", "requires", "complexity", "patentable", "branch", "categories"}
    assert all(set(entry) == expected_keys for entries in data["rnd_trees"].values() for entry in entries)
    smart_factory = next(entry for entry in data["rnd_trees"]["factory"] if entry["name"] == "smart_factory")
    assert smart_factory["label"] == "Smart Factory"
    assert smart_factory["patentable"] is True
    assert smart_factory["requires"] == ["robotik", "prognose_software"]
    json.dumps(data)


def test_rnd_trees_empty_when_trees_off():
    from market_sim.dashboard_data import _rnd_trees

    config = load_market_config()
    config = config.model_copy(update={
        "research": config.research.model_copy(update={"trees_enabled": False})
    })
    assert _rnd_trees(config) == {}


def test_rnd_facts_in_texts():
    data = {
        "firms": {
            "a": {
                "id": "a",
                "name": "Alpha",
                "stage": "factory",
                "yearly": [{
                    "year": 1,
                    "revenue": 0,
                    "profit": 0,
                    "cash_flows": {"schadenersatz:b": 40e6},
                    "events": [],
                }],
                "events": [],
            },
            "b": {
                "id": "b",
                "name": "Beta",
                "stage": "factory",
                "yearly": [{
                    "year": 1,
                    "revenue": 0,
                    "profit": 0,
                    "cash_flows": {"schadenersatz:a": -40e6},
                    "events": [],
                }],
                "events": [],
            },
        },
        "system": [{"year": 1, "total_profit": 2, "service_level": 0.9}],
        "events": [],
        "rnd_trees": {
            "factory": [
                {"name": "robotik", "label": "Robotik"},
                {"name": "smart_factory", "label": "Smart Factory"},
            ],
        },
        "rnd": [
            {"firm": "a", "tree": "factory", "step": "research", "stage": "smart_factory",
             "success": True, "end_year": 1},
            {"firm": "a", "tree": "factory", "step": "implementation", "stage": "robotik",
             "end_year": 1},
        ],
        "patents": [{
            "tree": "factory",
            "stage": "smart_factory",
            "holder": "a",
            "granted_year": 1,
            "expires_year": 6,
            "fee": 7e6,
            "status": "active",
            "end_year": None,
        }],
        "offence_ledger": [{
            "firm": "b",
            "offence": "patentverletzung",
            "year": 1,
            "fine": 5e6,
            "compensation": 40e6,
            "holder": "a",
        }],
    }

    facts_a = firm_facts(data, "a")
    assert "Forschungsstufen umgesetzt: 1 (Robotik)" in facts_a
    assert "Patent auf Smart Factory von Jahr 1 bis Jahr 6, Gebühr 7 Mio. CHF" in facts_a
    assert "Schadenersatz erhalten: 40 Mio. CHF" in facts_a

    facts_b = firm_facts(data, "b")
    assert "Schadenersatz bezahlt: 40 Mio. CHF" in facts_b
    assert "Patentverletzung entdeckt in Jahr 1" in facts_b

    year_text = year_facts(data, 1)
    assert "Patent erteilt: Alpha für Smart Factory bis Jahr 6" in year_text
    assert ("Patentverletzung entdeckt: Beta, Busse 5 Mio. CHF, Schadenersatz "
            "40 Mio. CHF an Alpha") in year_text
    assert unchecked_numbers(year_text, year_text) == []

    legacy_data = data.copy()
    for key in ("rnd", "patents", "offence_ledger", "rnd_trees"):
        legacy_data.pop(key)
    assert isinstance(firm_facts(legacy_data, "a"), str)
    assert isinstance(year_facts(legacy_data, 1), str)


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional for Python-only installations")
def test_phase27_javascript(dashboard_data, tmp_path):
    html_path = write_dashboard_html(dashboard_data, tmp_path / "d.html")
    html = html_path.read_text(encoding="utf-8")

    assert "__RND__" not in html
    assert "function renderRndTrees" in html
    assert 'id="rd-tree"' in html
    assert 'id="rd-patents"' in html
    assert 'id="fi-rnd"' in html
    assert 'id="st-patents"' in html
    assert "'rd-patents'" in html

    tests_dir = Path(__file__).parent
    market_sim_dir = tests_dir.parent
    subprocess.run(
        ["node", str(tests_dir / "dashboard_phase27_check.cjs"),
         str(market_sim_dir / "dashboard_rnd.js"), str(html_path)],
        check=True,
        capture_output=True,
        text=True,
    )
