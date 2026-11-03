"""Year-end entry rules and deterministic draws."""

from market_sim.run import build_runner
from market_sim.models import STAGES
from market_sim.checkpoint import save_checkpoint, load_checkpoint


def test_forced_entries_and_stage_caps():
    runner, _ = build_runner(years=3, days_per_year=2)
    cfg = runner.config.market_entry
    cfg.base_probability = cfg.max_probability = 1.0
    cfg.max_firms_per_stage = {s: len(runner.network.firms_in(s)) + 1 for s in STAGES}
    state = runner.start()
    runner.run_year(state)
    assert state.system_kpis[-1].market_entries == 4
    for stage in STAGES:
        firm = runner.network.firm(f"{stage}_e01")
        assert firm.inventory == firm.backlog == 0
        assert firm.suppliers == []
        assert cfg.start_reputation[0] <= firm.reputation <= cfg.start_reputation[1]
    runner.run_year(state)
    assert state.system_kpis[-1].market_entries == 0


def test_disabled_entries_still_consume_fixed_stage_draws():
    runner, _ = build_runner(days_per_year=2)
    runner.config.market_entry.enabled = False
    state = runner.start()
    before = len(runner._firms())
    runner.run_year(state)
    assert len(runner._firms()) == before
    assert state.system_kpis[-1].market_entries == 0


def test_fixed_draw_budget_and_checkpoint_resume(tmp_path):
    import random

    runner, _ = build_runner(years=4, days_per_year=3, seed=12)
    runner.config.market_entry.base_probability = 1
    runner.config.market_entry.max_probability = 1
    state = runner.start()
    runner.run_year(state)
    reference = random.Random("phase1-12")
    for _ in range(3 * len(STAGES) + 2 * len(runner._firms())):
        reference.random()
    assert runner._phase1_rng.getstate() == reference.getstate()
    path = save_checkpoint(runner, state, tmp_path / "phase1.pkl")
    resumed, restored = load_checkpoint(path)
    full = runner.continue_run(state, 4)
    fork = resumed.continue_run(restored, 4)
    assert full.annual_reports == fork.annual_reports
    assert full.system_kpis == fork.system_kpis
    assert full.events == fork.events
    assert full.final_result == fork.final_result
    assert full.daily_series == fork.daily_series


def test_entry_template_cash_and_name_cycle():
    runner, _ = build_runner(days_per_year=2)
    cfg = runner.config.market_entry
    cfg.base_probability = cfg.max_probability = 1
    runner.config.strategy_change.enabled = False
    state = runner.start()
    stage = "retailer"
    cfg.names[stage] = ["Aare"]
    initial_mean = runner._entry_cash[stage]
    runner.run_year(state)
    first = runner.network.firm("retailer_e01")
    assert first.cash == initial_mean * cfg.start_cash_fraction
    assert runner.env.runtimes[first.id].initial_cash == first.cash * runner.config.costs.initial_cash_scale
    runner.run_year(state)
    assert runner.network.firm("retailer_e02").name == "Aare 2"
