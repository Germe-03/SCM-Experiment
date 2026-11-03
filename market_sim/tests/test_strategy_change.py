"""Strategy eligibility, selection and lockout."""

from dataclasses import replace

import pytest

from market_sim.run import build_runner


@pytest.mark.parametrize("explore", [0.0, 1.0])
def test_two_bad_years_switch_and_lockout(explore):
    runner, _ = build_runner(days_per_year=2)
    runner.config.market_entry.enabled = False
    runner.config.strategy_change.explore_probability = explore
    state = runner.start()
    runner.run_year(state)
    firm = runner.network.firm("retailer_01")
    runtime = runner.env.runtimes[firm.id]
    runtime.consecutive_bad_years = 0
    old = firm.archetype
    for f in runner.network.firms_in("retailer"):
        state.summaries[-1][f.id] = replace(state.summaries[-1][f.id], revenue=1000,
                                           profit=-100 if f.id == firm.id else 100)
        state.annual_reports[-1][f.id] = state.annual_reports[-1][f.id].model_copy(update={
            "archetype": old if f.id == firm.id else "premium", "revenue": 1000,
            "profit": -100 if f.id == firm.id else 100,
        })
    runner._change_strategies(state)
    assert firm.archetype == old
    state.year += 1
    runner._change_strategies(state)
    assert firm.archetype != old
    if not explore:
        assert firm.archetype == "premium"
    event = [e for e in state.events if e["firm"] == firm.id and e["event"] == "strategy_change"][-1]
    assert ("ausprobiert" if explore else "nachgeahmt") in event["details"]
    switched = firm.archetype
    for _ in range(3):
        state.year += 1
        runner._change_strategies(state)
        assert firm.archetype == switched
