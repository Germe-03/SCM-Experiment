"""Seed-0 reference values captured before the Phase-0 refactor."""

from market_sim.run import run_simulation
from market_sim.config import load_market_config
from market_sim.models import load_firms


def test_seed_zero_ten_year_reference_is_exact() -> None:
    config = load_market_config()
    for feature in (config.market_entry, config.bank, config.strategy_change):
        feature.enabled = False
    config.policy.max_backlog_days = None
    config.consumer_model = "segments"
    config.long_run.enabled = False
    config.events.types = [t for t in config.events.types if t.type in {"heat_summer", "harvest_failure", "recall"}]
    config.categories.enabled = False
    config.state.enabled = False
    network = load_firms()
    for stage in network.stages:
        stage.firms = [f for f in stage.firms if f.category == "beer" and not f.importer]
    result = run_simulation(years=10, seed=0, config=config, network=network)
    market_events = [
        (event["year"], event["day"], event["firm"], event["event"])
        for event in result.events
        if event["event"] in {"heat_summer", "harvest_failure", "recall"}
    ]

    assert market_events == [
        (1, 156, "", "heat_summer"),
        (3, 1, "distributor_01", "recall"),
        (4, 1, "retailer_02", "recall"),
        (6, 150, "", "heat_summer"),
        (7, 162, "", "heat_summer"),
        (9, 164, "", "heat_summer"),
    ]
    assert result.system_kpis[0].total_profit == 781072015.9052114
    assert result.system_kpis[4].service_level == 0.9994299964374778
    assert result.system_kpis[9].bullwhip_ratio == 139.68856510362642
    assert result.final_result.total_profit == 5806633636.570863
    assert result.final_result.cumulative_lost_sales == 26748
    assert result.final_result.firm_results["retailer_01"].cash == 232755293.42382574

