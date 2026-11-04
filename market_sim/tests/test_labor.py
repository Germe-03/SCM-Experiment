"""Phase 11: regional labour markets."""

from market_sim.run import build_runner


def _runner():
    runner, _ = build_runner(1, 0, days_per_year=20)
    state = runner.start()
    runner.continue_run(state, 1)
    return runner, state


def test_pools_follow_population_and_hiring_is_limited_by_free_workers():
    runner, _ = _runner()
    labor = runner.labor
    geo = runner.env.geography
    assert set(labor.pool) == set(geo.population)
    big, small = max(geo.population, key=geo.population.get), min(geo.population, key=geo.population.get)
    assert labor.pool[big] > labor.pool[small]
    for region in labor.pool:
        labor.pool[region] = 0.0001  # no free workers anywhere
    active = [f for f in runner._firms() if runner.env.runtimes[f.id].active]
    before = sum(f.employees for f in active)
    labor.year_start(runner)
    # Poaching may move staff between firms, but nobody new is hired.
    assert sum(f.employees for f in active) <= before
    assert labor.stats["hires"] == 0


def test_tight_market_raises_wages_and_poorly_paid_staff_leave():
    runner, _ = _runner()
    labor = runner.labor
    region = runner.network.firm("retailer_01").region
    members = [f for f in runner._firms() if runner.env.runtimes[f.id].active and f.region == region]
    labor.pool[region] = sum(f.employees for f in members) * 0.5  # very tight
    low = min(members, key=lambda f: f.wage_level)
    low.wage_level *= 0.5
    low.employees = max(low.employees, 40)
    before_index = labor.wage_index[region]
    labor.year_start(runner)
    assert labor.wage_index[region] > before_index
    assert labor.stats["poached_workers"] > 0
