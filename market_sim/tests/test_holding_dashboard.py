"""Phase 42: holdings in the dashboard (data export and JavaScript rendering)."""

from pathlib import Path
import shutil
import subprocess

import pytest

from market_sim.dashboard import write_dashboard_html
from market_sim.tests.test_dashboard import _data


def test_dashboard_data_exports_holding_groups_and_html_contains_view(tmp_path):
    data = _data()
    assert "holding_groups" in data and "holding_log" in data
    path = write_dashboard_html(data, tmp_path / "holdings.html")
    html = path.read_text(encoding="utf-8")
    for marker in ("renderHoldingGroups", 'id="hg-firms"', 'id="hg-compare"', 'id="hg-stocks"'):
        assert marker in html
    assert "__HOLDINGS__" not in html


@pytest.mark.skipif(shutil.which("node") is None, reason="Node is optional for Python-only installations")
def test_holding_view_renders_subsidiaries_in_three_tabs():
    directory = Path(__file__).parent
    subprocess.run(["node", str(directory / "dashboard_phase42_check.cjs"),
                    str(directory.parent / "dashboard_holdings.js")],
                   check=True, capture_output=True, text=True)
