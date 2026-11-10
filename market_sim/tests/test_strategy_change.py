"""Phase 52: firms are classified into strategies from their behaviour, they do not choose one."""

from market_sim.classification import classify, distances, observe, prototype
from market_sim.policies import FirmPolicy
from market_sim.run import build_runner


def test_prototypes_classify_to_themselves():
    for stage in ("retailer", "factory", "wholesaler", "distributor"):
        for archetype in FirmPolicy._PRESETS:
            assert classify(stage, prototype(stage, archetype)) == archetype
            assert distances(stage, prototype(stage, archetype))[archetype] == 0


def test_hysteresis_keeps_current_label_when_gain_is_small():
    std, rel = prototype("retailer", "standard"), prototype("retailer", "reliable")
    features = [0.6 * a + 0.4 * b for a, b in zip(std, rel)]
    dist = distances("retailer", features)
    assert dist["standard"] < dist["reliable"]
    assert classify("retailer", features, current="reliable", hysteresis=0.0) == "standard"
    assert classify("retailer", features, current="reliable", hysteresis=0.5) == "reliable"


def test_tendency_is_stable_over_years():
    runner, _ = build_runner(days_per_year=2)
    runner.config.market_entry.enabled = False
    state = runner.start()
    tendencies = {f.id: f.tendency for f in runner._firms()}
    assert all(f.tendency == f.archetype for f in runner._firms())
    runner.run_year(state)
    runner.run_year(state)
    assert {f.id: f.tendency for f in runner._firms()} == tendencies
    firm = runner.network.firm("retailer_01")
    assert observe(firm, runner.strategies[firm.id], runner.config)


def test_classification_changes_label_and_logs_event():
    runner, _ = build_runner(days_per_year=2)
    runner.config.market_entry.enabled = False
    state = runner.start()
    runner.run_year(state)
    firm = runner.network.firm("retailer_01")
    assert runner.env.runtimes[firm.id].active
    old = firm.archetype
    target = "premium" if old != "premium" else "low_cost"
    band = runner.config.stage_prices[firm.stage]
    low, high = max(band.min, 0.8 * band.base), min(band.max, 1.3 * band.base)
    proto = prototype(firm.stage, target)
    strategy = runner.strategies[firm.id]
    price = low + proto[0] * (high - low)
    runner.strategies[firm.id] = strategy.model_copy(update={
        "base_price": price, "min_price": min(strategy.min_price, price),
        "max_price": max(strategy.max_price, price),
        "wage_level": firm.initial_wage_level * proto[1],
        "r_and_d_budget": firm.initial_r_and_d_budget * proto[2],
        "target_quality": proto[3], "target_safety_stock_days": int(proto[4]),
        "risk_tolerance": proto[5], "overtime_level": proto[6],
    })
    assert runner._change_strategies(state) >= 1
    assert firm.archetype == target
    assert firm.tendency == old
    event = [e for e in state.events if e["firm"] == firm.id and e["event"] == "strategy_change"][-1]
    assert "Neu eingestuft" in event["details"]
    assert state.annual_reports[-1][firm.id].archetype == target
