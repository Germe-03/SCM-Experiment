"""Phase 29: couriers enter, compete with the Post and can go bankrupt."""

from market_sim.config import load_market_config
from market_sim.couriers import CourierMarket
from market_sim.run import build_runner


def _config(enabled=True, **couriers):
    config = load_market_config()
    c = config.carriers
    carriers = c.model_copy(update={
        "enabled": True,
        "couriers": c.couriers.model_copy(
            update={"enabled": enabled, **couriers}
        ),
    })
    return config.model_copy(update={"carriers": carriers})


def _market(**couriers):
    runner, _ = build_runner(1, 0, days_per_year=10, config=_config(**couriers))
    state = runner.start()
    runner.continue_run(state, 1)
    return runner, state, runner.env.geography.carriers


def _set_region_volume(market):
    market.region_unit_km = {
        region: 5e7 for region in market.region_unit_km
    }


def test_no_margin_means_no_entry():
    runner, state, market = _market(
        entry_probability=1.0,
        min_margin=10.0,
    )

    for _ in range(3):
        _set_region_volume(market)
        market.year_end(runner, state)

    assert not any(courier.active for courier in market.couriers.values())
    assert not any(event["event"] == "courier_entry" for event in state.events)


def test_couriers_start_in_dense_regions():
    runner, state, market = _market(
        entry_probability=1.0,
        max_entries_per_year=1,
    )

    _set_region_volume(market)
    market.year_end(runner, state)

    active = [courier for courier in market.couriers.values() if courier.active]
    assert len(active) == 1
    assert active[0].regions in (["genfersee"], ["zuerich"])

    region = active[0].regions[0]
    assert market.margin(region, runner, 5e7) > market.margin(
        "tessin", runner, 5e7
    )


def test_courier_can_go_bankrupt():
    runner, state, market = _market(
        entry_probability=1.0,
        max_entries_per_year=1,
    )

    _set_region_volume(market)
    market.year_end(runner, state)
    courier = next(iter(market.couriers.values()))
    courier.cash = -1e9
    market.ccfg = market.ccfg.model_copy(update={"entry_probability": 0.0})

    _set_region_volume(market)
    market.year_end(runner, state)

    assert not courier.active
    assert any(
        event["event"] == "courier_bankrupt" and event["firm"] == courier.id
        for event in state.events
    )
    supplier = runner.network.firm("wholesaler_01")
    customer = runner.network.firm("retailer_01")
    assert market.carrier_for(supplier, customer) is market.post


def _choice_result(risk_tolerance, learned_delay, damage):
    runner, state, market = _market(
        entry_probability=1.0,
        max_entries_per_year=1,
    )

    _set_region_volume(market)
    market.year_end(runner, state)
    courier = next(iter(market.couriers.values()))

    courier.regions = ["zuerich"]
    info = market.courier_info[courier.id]
    info["price"] = {"zuerich": 0.0}
    info["loss_years"] = {"zuerich": 0}
    info["damage"] = damage
    info["delay"] = 0.10

    market.ccfg = market.ccfg.model_copy(update={
        "entry_probability": 0.0,
        "variable_rate": 0.0,
        "fixed_cost_per_day_per_region": 0.0,
        "undercut": [1.0, 1.0],
        "min_markup": 0.0,
        "expand_probability": 0.0,
        "takeover_probability": 0.0,
    })
    carriers_config = market.config.carriers.model_copy(
        update={"switching_cost_share": 0.0}
    )
    market.config = market.config.model_copy(
        update={"carriers": carriers_config}
    )

    firm = runner.network.firm("wholesaler_01")
    firm.transport_mode = "service"
    strategy = runner.strategies[firm.id]
    runner.strategies[firm.id] = strategy.model_copy(
        update={"risk_tolerance": risk_tolerance}
    )

    for retailer in runner.network.firms_in("retailer"):
        if runner.env.runtimes[retailer.id].active:
            retailer.region = "zuerich"

    market.contracts.clear()  # Phase 54: earlier contracts must not block this choice
    if learned_delay is not None:
        market.experience[(firm.id, courier.id)] = [1.0, learned_delay]

    _set_region_volume(market)
    market.year_end(runner, state)

    return market.assignment[(firm.id, "zuerich")], courier.id


def test_unreliable_cheap_courier_loses_risk_averse_customers():
    risk_averse_assignment, _ = _choice_result(
        risk_tolerance=0.0,
        learned_delay=30.0,
        damage=0.03,
    )
    risk_loving_assignment, courier_id = _choice_result(
        risk_tolerance=1.0,
        learned_delay=None,
        damage=0.0,
    )

    assert risk_averse_assignment == "post"
    assert risk_loving_assignment == courier_id


def test_couriers_disabled_uses_carrier_market():
    runner, _ = build_runner(
        1,
        0,
        days_per_year=10,
        config=_config(enabled=False),
    )
    runner.start()

    assert not isinstance(runner.env.geography.carriers, CourierMarket)


def test_courier_runs_are_deterministic():
    runner_a, _ = build_runner(
        2, 1, days_per_year=30, config=_config(entry_probability=0.5)
    )
    result_a = runner_a.run(2)

    runner_b, _ = build_runner(
        2, 1, days_per_year=30, config=_config(entry_probability=0.5)
    )
    result_b = runner_b.run(2)

    assert result_a.carriers == result_b.carriers
    assert result_a.events == result_b.events


def test_contract_blocks_carrier_change_until_it_expires():
    runner, state, market = _market(entry_probability=0.0)
    firm = runner.network.firm("wholesaler_01")
    firm.transport_mode = "service"
    key = (firm.id, firm.region)
    market.assignment.clear()
    market.contracts.clear()
    market.assignment[key] = market.post.id
    market.contracts[key] = state.year + 2
    assert market.service_locked(firm.id, state.year)
    assert market.service_locked(firm.id, state.year + 1)
    assert not market.service_locked(firm.id, state.year + 2)
    del market.assignment[key]
    assert not market.service_locked(firm.id, state.year)
