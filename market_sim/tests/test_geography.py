"""Phase 5: regions, transport, own fleet or service, expansion and new sites."""

import pytest

from market_sim.run import build_runner


def _runner(days=10):
    runner, _ = build_runner(1, 0, days_per_year=days)
    state = runner.start()
    return runner, state


def test_every_firm_has_a_region_and_distance_is_symmetric():
    runner, _ = _runner()
    geo = runner.env.geography
    firms = [f for s in runner.network.stages for f in s.firms]
    assert all(f.region in geo.regions for f in firms)
    a, b = runner.network.firm("retailer_01"), runner.network.firm("wholesaler_01")
    assert geo.km(a, b) == pytest.approx(geo.km(b, a))
    assert geo.km(a, a) == pytest.approx(geo.cfg.local_km)


def test_service_costs_more_per_km_than_own_fleet():
    runner, _ = _runner()
    geo = runner.env.geography
    supplier, customer = runner.network.firm("wholesaler_01"), runner.network.firm("retailer_01")
    supplier.transport_mode = "own"
    own = geo.unit_transport_cost(supplier, customer)
    supplier.transport_mode = "service"
    assert geo.unit_transport_cost(supplier, customer) == pytest.approx(own * geo.cfg.service_rate / geo.cfg.own_rate)


def test_damage_hits_only_own_fleet_shipments():
    runner, _ = _runner()
    env, geo = runner.env, runner.env.geography
    geo.cfg.damage_probability = 1.0
    supplier, customer = runner.network.firm("wholesaler_01"), runner.network.firm("retailer_01")
    supplier.transport_mode = "own"
    parcel = {"alpen_lager": 100}
    assert geo.ship(env, supplier, customer, parcel) == 5 and parcel["alpen_lager"] == 95
    supplier.transport_mode = "service"
    parcel = {"alpen_lager": 100}
    assert geo.ship(env, supplier, customer, parcel) == 0 and parcel["alpen_lager"] == 100


def test_populous_region_gives_a_larger_catchment():
    runner, _ = _runner()
    geo = runner.env.geography
    retailers = runner.network.firms_in("retailer")
    big, small = retailers[0], retailers[1]
    big.region, small.region = "zuerich", "tessin"
    catch = geo.catchment([big, small])
    assert catch[big.id] > catch[small.id]
    small.extra_regions.append("zuerich")
    assert geo.catchment([big, small])[small.id] > catch[small.id]


def test_investment_waits_for_a_tight_stage_and_adds_capacity_when_done():
    runner, state = _runner()
    geo, env = runner.env.geography, runner.env
    firm = runner.network.firm("retailer_01")
    before = firm.capacity
    geo._start(env, firm, "expand", 5, 1_000_000.0, 10, state)
    assert geo.depreciation[firm.id][0][0] == pytest.approx(1_000_000.0 / (geo.cfg.depreciation_years * 10))
    env.period = geo.projects[0][0]
    geo._finish_projects(runner, state)
    assert firm.capacity == before + 5
    assert state.events[-1]["event"] == "expand_finished"


def test_entrants_settle_where_their_stage_is_thinnest():
    runner, _ = _runner()
    geo = runner.env.geography
    region = geo.entrant_region(runner, "wholesaler")
    load = {r: 0 for r in geo.regions}
    for f in runner.network.firms_in("wholesaler"):
        load[f.region] += 1
    assert load[region] == min(load.values())
