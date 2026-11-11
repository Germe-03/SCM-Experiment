"""Truck dealers invest surplus cash in minority stakes and sell bad ones."""

from dataclasses import replace

from market_sim.run import build_runner


def _setup():
    runner, _ = build_runner(2, 0, days_per_year=20)
    state = runner.start()
    runner.continue_run(state, 1)
    return runner, state


def _only_profitable(runner, state, ids):
    summaries = state.summaries[-1]
    for fid, s in list(summaries.items()):
        summaries[fid] = replace(s, profit=1e7 if fid in ids else -1.0)


def test_dealer_with_cash_buys_a_stake():
    runner, state = _setup()
    dealers = runner._dealers()
    assert dealers
    dealer = dealers[0].id
    target = "wholesaler_01"
    _only_profitable(runner, state, {dealer, target})
    runner.env.runtimes[dealer].cash = 1e12
    h = runner.holdings
    h.cfg.buy_probability = 1.0
    h.cfg.via_bank = False
    h.stakes = {}
    h.year_end(runner, state)
    assert any(o == dealer for (o, _t) in h.stakes)
    assert any(r["owner"] == dealer and r["action"] == "stake_bought" for r in h.history)


def test_dealer_stake_is_sold_on_loss():
    runner, state = _setup()
    dealer = runner._dealers()[0].id
    target = "wholesaler_01"
    _only_profitable(runner, state, set())
    h = runner.holdings
    h.cfg.buy_probability = 0.0
    h.stakes = {(dealer, target): 0.2}
    runner.env.runtimes[target].consecutive_loss_years = h.cfg.sell_after_loss_years
    h.year_end(runner, state)
    assert (dealer, target) not in h.stakes
    assert any(r["owner"] == dealer and r["action"] == "stake_sold" for r in h.history)
