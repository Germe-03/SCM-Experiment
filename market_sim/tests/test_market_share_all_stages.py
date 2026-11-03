"""Stage shares use revenue; retail keeps consumer units."""

import pytest

from market_sim.models import STAGES
from market_sim.run import build_runner


def test_revenue_shares_category_shares_and_hhi():
    runner, _ = build_runner(2, 0, days_per_year=10)
    runner.config.bankruptcy.enabled = False
    result = runner.run(2)
    for reports, kpi in zip(result.annual_reports, result.system_kpis):
        for stage in STAGES:
            firms = runner.network.firms_in(stage)
            total = sum(reports[f.id].revenue for f in firms)
            assert sum(reports[f.id].market_share for f in firms) == pytest.approx(1 if total else 0)
            if stage != "retailer":
                for f in firms:
                    assert reports[f.id].market_share == pytest.approx(reports[f.id].revenue / total if total else 0)
                assert getattr(kpi, f"hhi_{stage}") == pytest.approx(sum(reports[f.id].market_share ** 2 for f in firms))
        for category in ("beer", "wine", "spirits"):
            producers = [f for f in runner.network.firms_in("factory") if f.category == category]
            revenue = sum(reports[f.id].revenue for f in producers)
            for f in producers:
                assert reports[f.id].category_share == pytest.approx(reports[f.id].revenue / revenue if revenue else 0)


def test_inactive_upstream_firm_has_no_share():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.env.runtimes["wholesaler_01"].active = False
    result = runner.continue_run(state, 1)
    assert result.annual_reports[0]["wholesaler_01"].market_share == 0
    assert sum(result.annual_reports[0][f.id].market_share for f in runner.network.firms_in("wholesaler")) == pytest.approx(1)
