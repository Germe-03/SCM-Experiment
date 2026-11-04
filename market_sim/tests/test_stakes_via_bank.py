"""Phase 18: small stakes go through the exchange and the house bank."""

from types import SimpleNamespace

import pytest

from market_sim.run import build_runner


def _runner_with_two_profitable_firms(*, listed, min_stake, max_stake, via_bank=True):
    runner, _ = build_runner(years=1, seed=0, days_per_year=4)
    holdings = runner.holdings
    cfg = holdings.cfg
    cfg.buy_probability = 1.0
    cfg.min_stake = min_stake
    cfg.max_stake = max_stake
    cfg.cash_cover = 0.0
    cfg.small_stake_limit = 0.10
    cfg.via_bank = via_bank
    cfg.broker_fee = max(cfg.broker_fee, 0.01)

    if listed:
        runner.config.stock_market.tradable_from_year = 1

    state = runner.start()
    banking = runner.env.banking
    firms_with_accounts = sorted(
        f.id for f in runner._firms()
        if runner.env.runtimes[f.id].active and banking.accounts.get(f.id)
    )
    owner, target = firms_with_accounts[:2]
    profitable = {owner, target}
    state.summaries = [{
        f.id: SimpleNamespace(profit=1e8 if f.id in profitable else 0.0)
        for f in runner._firms()
    }]
    for runtime in runner.env.runtimes.values():
        runtime.cash = 1e15

    if listed:
        runner.stock_market.daily(runner, state, 1, 0, 0)

    return runner, state, owner, target


def test_small_stake_bought_on_exchange_with_fee():
    runner, state, _, _ = _runner_with_two_profitable_firms(
        listed=True, min_stake=0.02, max_stake=0.05
    )
    holdings = runner.holdings

    holdings.year_end(runner, state)

    new_stakes = [
        (buyer, target_id, share)
        for (buyer, target_id), share in holdings.stakes.items()
    ]
    assert new_stakes
    assert all(share < 0.10 for _, _, share in new_stakes)

    banks = runner.env.banking
    for buyer, target_id, _ in new_stakes:
        assert holdings.depot[(buyer, target_id)] == banks.primary_bank(buyer).id
        assert f"kapital_von:{buyer}" not in runner.env.runtimes[target_id].cash_flows

    assert sum(bank.fee_income for bank in banks.banks.values()) > 0
    bought_events = [event for event in state.events if event["event"] == "stake_bought"]
    assert bought_events
    assert all("an der Börse" in event["details"] for event in bought_events)


def test_unlisted_target_gets_no_small_stake():
    runner, state, _, _ = _runner_with_two_profitable_firms(
        listed=False, min_stake=0.02, max_stake=0.05
    )

    runner.holdings.year_end(runner, state)

    assert all(
        share >= runner.holdings.cfg.small_stake_limit
        for share in runner.holdings.stakes.values()
    )


def test_large_stake_is_direct_deal():
    runner, state, _, _ = _runner_with_two_profitable_firms(
        listed=True, min_stake=0.3, max_stake=0.3
    )
    holdings = runner.holdings

    holdings.year_end(runner, state)

    assert holdings.stakes
    for owner, target in holdings.stakes:
        assert holdings.stakes[(owner, target)] == pytest.approx(0.3)
        assert f"kapital_von:{owner}" in runner.env.runtimes[target].cash_flows
        assert (owner, target) not in holdings.depot


def test_via_bank_off_keeps_old_behaviour():
    runner, state, _, _ = _runner_with_two_profitable_firms(
        listed=False, min_stake=0.02, max_stake=0.05, via_bank=False
    )
    holdings = runner.holdings

    holdings.year_end(runner, state)

    assert holdings.stakes
    for owner, target in holdings.stakes:
        assert f"kapital_von:{owner}" in runner.env.runtimes[target].cash_flows
        assert (owner, target) not in holdings.depot
