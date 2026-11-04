"""S9 standalone metrics and runner reporting tests."""

import pytest

from market_sim.config import load_market_config
from market_sim.kpi import bullwhip_variance_ratio, herfindahl_index
from market_sim.models import load_firms
from market_sim.policies import policies_for_network
from market_sim.runner import SimulationRunner


@pytest.mark.parametrize("shares, expected", [
    ([0.5, 0.5], 0.5), ([1.0], 1.0), ([0.25] * 4, 0.25),
])
def test_herfindahl_known_inputs(shares, expected):
    assert herfindahl_index(shares) == pytest.approx(expected)


def test_bullwhip_variance_ratio():
    assert bullwhip_variance_ratio([1, 9, 1], [4, 4, 4]) == 1.0
    assert bullwhip_variance_ratio([0, 20, 0, 20], [4, 6, 4, 6]) > 1.0


def _run():
    config = load_market_config()
    config = config.model_copy(update={
        "simulation": config.simulation.model_copy(update={"days_per_year": 12})
    })
    network = load_firms()
    firms = [firm for stage in network.stages for firm in stage.firms]
    return SimulationRunner(
        network, config, policies_for_network(firms), seed=712,
    ).run(years=2)


def test_runner_emits_sane_reports_and_dynamic_reputation():
    result = _run()
    expected_firms = sum(len(stage.firms) for stage in result.network.stages)
    assert len(result.annual_reports) == len(result.system_kpis) == 2
    for reports, kpis in zip(result.annual_reports, result.system_kpis):
        assert len(reports) == expected_firms
        retailers = [report for report in reports.values()
                     if result.network.firm(report.firm_id).stage == "retailer"]
        # Stores and restaurants are separate markets, each adding up to 100 %.
        for channel in ("store", "restaurant"):
            assert sum(r.market_share for r in retailers
                       if result.network.firm(r.firm_id).channel == channel) == pytest.approx(1.0)
        for report in reports.values():
            assert 0 <= report.market_share <= 1
            assert 0 <= report.reputation <= 1
            assert 0 <= report.capacity_utilization <= 1
            assert all(0 <= value <= 1 for value in report.supplier_reliability.values())
        assert 0 <= kpis.market_concentration <= 1
        assert 0 <= kpis.service_level <= 1
    assert any(
        result.annual_reports[0][firm_id].reputation
        != result.annual_reports[1][firm_id].reputation
        for firm_id in result.annual_reports[0]
    )


def test_reporting_is_deterministic_for_fixed_seed():
    first, second = _run(), _run()
    assert [r.model_dump() for r in first.system_kpis] == [r.model_dump() for r in second.system_kpis]
    assert [
        {key: report.model_dump() for key, report in year.items()}
        for year in first.annual_reports
    ] == [
        {key: report.model_dump() for key, report in year.items()}
        for year in second.annual_reports
    ]
