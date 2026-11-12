"""Breweries cannot make soft drinks themselves, but may buy a soft drink firm as a subsidiary."""

from market_sim.tests._voluntary import boost_profit

from market_sim.holding_groups import category_allows_buy
from market_sim.run import build_runner
from market_sim.runner import YearSummary
from market_sim.tests.test_holding_groups import _runner, _summaries


def test_new_category_stage_removed():
    runner, _ = build_runner(1, 0, days_per_year=10)
    stages = {s.name: s for s in runner.config.research.trees["factory"]}
    assert "softdrinks_sortiment" not in stages
    assert not any(s.kind == "new_category" for s in stages.values())
    for s in stages.values():
        assert "softdrinks_sortiment" not in (s.requires or [])


def test_category_rule():
    assert category_allows_buy("beer", "beer")
    assert category_allows_buy("beer", "softdrinks")
    assert category_allows_buy("beer", "water")
    assert not category_allows_buy("softdrinks", "beer")
    assert not category_allows_buy("beer", "wine")


def test_brewery_buys_softdrink_firm_as_subsidiary():
    runner, state = _runner()
    env, actor = runner.env, runner.state_actor
    buyer = runner.network.firm("factory_01")
    target = runner.network.firm("softdrink_01")
    env.runtimes[target.id].consecutive_loss_years = 5
    env.runtimes[buyer.id].cash = 1e12
    runner.holdings.stakes = {}
    runner.config.state.block_share = 1.0
    runner.config.state.max_takeovers_per_stage = 5
    for firm in runner.network.firms_in("factory"):
        if firm.id not in (buyer.id, target.id):
            env.runtimes[firm.id].consecutive_loss_years = 0
    state.summaries.append(_summaries(runner, {}))
    boost_profit(state)  # voluntary takeovers need a clear gain
    runner.config.state.takeover_bid_probability = 1.0

    actor.takeovers(runner, state)

    group = runner.holding_groups.group_of(buyer.id)
    assert group is not None and target.id in group.subs
    assert env.runtimes[target.id].active
    assert runner.network.firm(target.id).category == "softdrinks"


def test_no_merger_across_categories():
    runner, state = _runner()
    mergers = runner.mergers
    runner.config.mergers.enabled = True
    beer = runner.network.firm("factory_01")
    soft = runner.network.firm("softdrink_01")
    # compatible() is local to year_end; check via a forced run that no merged firm mixes categories
    state.summaries.append(_summaries(runner, {}))
    boost_profit(state)  # voluntary takeovers need a clear gain
    runner.config.state.takeover_bid_probability = 1.0
    mergers.year_end(runner, state)
    for entry in mergers.log:
        ids = [entry.get(k) for k in ("a", "b") if entry.get(k)]
        cats = {runner.network.firm(i).category for i in ids if i in {f.id for f in runner._firms()}}
        assert len(cats) <= 1
    assert beer.category != soft.category
