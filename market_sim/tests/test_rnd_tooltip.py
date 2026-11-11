"""F&E-Baum: Tooltip, eindeutige Positionen, Kategorie-Filter und verrauschte Wirkungsschätzung."""

import shutil
import subprocess
from pathlib import Path

import pytest

from market_sim.run import build_runner
from market_sim.dashboard_data import _rnd_trees

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node fehlt")
def test_tree_layout_and_tooltip_js():
    out = subprocess.run(["node", str(ROOT / "tests" / "rnd_tooltip_check.cjs"), str(ROOT / "dashboard_rnd.js")],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr + out.stdout


def test_rnd_trees_export_has_tooltip_fields():
    runner, _ = build_runner(1, 0, days_per_year=10)
    trees = _rnd_trees(runner.config)
    if not trees:
        pytest.skip("Bäume aus")
    stage = next(iter(trees.values()))[0]
    for key in ("kind", "effect", "cost", "duration_days", "success_probability", "implementation_cost",
                "implementation_days", "requires", "patentable"):
        assert key in stage


def test_firm_sees_exact_effect_only_for_known_stages():
    runner, _ = build_runner(1, 0, days_per_year=10)
    lab = runner.lab
    firm = next(f for f in runner._firms() if lab.options(f))
    stage = next(s for s in lab.options(firm) if s.effect > 0)
    factor = lab.estimate_factor(firm.id, stage.name)
    assert 0.6 <= factor <= 1.4
    assert lab.estimate_factor(firm.id, stage.name) == factor
    assert lab.perceived_effect(firm, stage) == pytest.approx(stage.effect * factor)
    lab.progress.setdefault(firm.id, {})[stage.name] = "researched"
    assert lab.perceived_effect(firm, stage) == stage.effect
