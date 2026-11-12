"""Voluntary takeovers: offers list, wants_to_buy, player firms are never automatic parties."""

from market_sim.run import build_runner
from market_sim.runner import YearSummary
from market_sim.state import wants_to_buy
from market_sim.tests._voluntary import boost_profit


def _setup():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.continue_run(state, 1)
    runner.holdings.stakes = {}
    runner.holding_groups = None
    runner.config.state.takeover_bid_probability = 1.0
    summaries = {f.id: YearSummary(revenue=1.0, profit=1.0, avg_inventory=0, avg_backlog=0, lost_sales=0,
                                   service_level=1, avg_sell_price=1, quality=0.5,
                                   capacity_utilization=0.5, cash=0)
                 for s in runner.network.stages for f in s.firms}
    state.summaries.append(summaries)
    return runner, state, summaries


def test_offer_is_listed_and_nobody_buys_when_price_too_high():
    runner, state, summaries = _setup()
    target, buyer = runner.network.firm("wholesaler_02"), runner.network.firm("wholesaler_01")
    runner.env.runtimes[target.id].consecutive_loss_years = 5
    runner.env.runtimes[buyer.id].cash = 1e12
    runner.state_actor.takeovers(runner, state)  # profit 1 -> value far below price
    assert any(o["target"] == target.id for o in runner.takeover_offers)
    assert runner.env.runtimes[target.id].active
    assert not any(e["event"] == "takeover" for e in state.events)


def test_buyer_with_clear_gain_buys_voluntarily():
    runner, state, summaries = _setup()
    target, buyer = runner.network.firm("wholesaler_02"), runner.network.firm("wholesaler_01")
    runner.env.runtimes[target.id].consecutive_loss_years = 5
    runner.env.runtimes[buyer.id].cash = 1e12
    boost_profit(state, only={buyer.id})
    summaries = state.summaries[-1]
    runner.state_actor.takeovers(runner, state)
    assert not runner.env.runtimes[target.id].active


def test_zero_probability_means_no_bid():
    runner, state, summaries = _setup()
    runner.config.state.takeover_bid_probability = 0.0
    target, buyer = runner.network.firm("wholesaler_02"), runner.network.firm("wholesaler_01")
    runner.env.runtimes[buyer.id].cash = 1e12
    boost_profit(state, only={buyer.id})
    summaries = state.summaries[-1]
    assert not wants_to_buy(runner, buyer, target, 1.0, year=1, seed=0, summary=summaries[buyer.id])


def test_player_firms_are_never_buyers_or_targets():
    runner, state, summaries = _setup()
    target, buyer = runner.network.firm("wholesaler_02"), runner.network.firm("wholesaler_01")
    runner.env.runtimes[target.id].consecutive_loss_years = 5
    runner.env.runtimes[buyer.id].cash = 1e12
    boost_profit(state, only={buyer.id})
    summaries = state.summaries[-1]
    runner.player_choices = {target.id: object()}
    runner.state_actor.takeovers(runner, state)
    assert runner.env.runtimes[target.id].active
    assert not any(o["target"] == target.id for o in runner.takeover_offers)
    runner.player_choices = {buyer.id: object()}
    assert not wants_to_buy(runner, buyer, target, 1.0, year=1, seed=0, summary=summaries[buyer.id])
