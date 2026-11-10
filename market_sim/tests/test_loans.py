"""Phase 55: investment loans, bankruptcy write-off, deposit rates tied to the policy rate."""

import pytest

from market_sim.config import load_market_config
from market_sim.run import build_runner


def _runner(**loans):
    config = load_market_config()
    config.banking.loans.enabled = True
    for key, value in loans.items():
        setattr(config.banking.loans, key, value)
    runner, _ = build_runner(1, 0, days_per_year=10, config=config)
    runner.start()
    return runner


def _firm(runner, cash=50e6, revenue=100e6):
    rt = runner.env.runtimes["retailer_01"]
    rt.cash, rt.last_year_revenue = cash, revenue
    rt.consecutive_loss_years = 0
    return rt


def test_loan_rate_is_policy_rate_plus_margin_plus_premium():
    runner = _runner()
    banking, rt = runner.env.banking, _firm(runner)
    offer, reason = banking.loan_offer("retailer_01", rt, 10e6, "expand", 0.02)
    assert offer is not None, reason
    bank, rate, years = offer
    assert bank is banking.primary_bank("retailer_01")
    assert rate > 0.02 + bank.margin
    assert rate <= runner.config.banking.loans.max_rate
    assert years == 8
    weak, _ = banking.loan_offer("retailer_01", _firm(runner, cash=-20e6), 10e6, "expand", 0.02)
    worse_rate = weak[1] if weak else rate + 1
    assert worse_rate >= rate


def test_bank_refuses_beyond_its_room_and_firms_in_trouble():
    runner = _runner()
    banking, rt = runner.env.banking, _firm(runner)
    bank = banking.primary_bank("retailer_01")
    room = banking.lending_room(bank)
    assert banking.loan_offer("retailer_01", rt, room * 2 + 1, "expand", 0.01)[0] is None
    rt.consecutive_loss_years = 2
    assert banking.loan_offer("retailer_01", rt, 1e6, "expand", 0.01)[0] is None


def test_grant_and_repay_loan():
    runner = _runner()
    env, banking, rt = runner.env, runner.env.banking, _firm(runner)
    bank = banking.primary_bank("retailer_01")
    events = []
    loan = banking.grant_loan("retailer_01", rt, bank, 10e6, 0.03, 5, "expand", 3, 10, events)
    assert rt.cash == pytest.approx(60e6)
    assert banking.term_debt("retailer_01") == pytest.approx(10e6)
    assert events[0]["event"] == "loan_granted"
    banking.aggregate(env.runtimes)
    assert bank.loans >= 10e6
    banking.repay_loans(env.runtimes, 3)  # same year: nothing due yet
    assert loan.outstanding == pytest.approx(10e6)
    banking.repay_loans(env.runtimes, 4)
    assert loan.outstanding == pytest.approx(8e6)
    assert rt.cash == pytest.approx(58e6)
    # Daily interest goes to the bank.
    before = bank.interest_income
    assert banking.accrue_loan_interest("retailer_01") == pytest.approx(8e6 * 0.03 / 365)
    assert bank.interest_income > before


def test_bankruptcy_writes_off_remaining_loan():
    runner = _runner()
    env, banking, rt = runner.env, runner.env.banking, _firm(runner)
    bank = banking.primary_bank("retailer_01")
    banking.grant_loan("retailer_01", rt, bank, 10e6, 0.03, 5, "expand", 1, 10, [])
    rt.cash = 0.0
    before = bank.write_offs
    env.close_firm("retailer_01")
    assert not banking.loans
    assert bank.write_offs - before == pytest.approx(10e6 * runner.config.banking.loss_given_default)
    assert bank.loan_write_offs == pytest.approx(10e6 * runner.config.banking.loss_given_default)


def test_arrange_funding_prefers_cash_but_uses_credit_when_poor():
    runner = _runner(preference_base=0.0, preference_risk=0.0)
    env, banking, rt = runner.env, runner.env.banking, _firm(runner, cash=500e6, revenue=100e6)
    assert env.arrange_funding("retailer_01", 10e6, "expand", 2.0)
    assert not banking.loans
    rt.cash = 5e6
    assert env.arrange_funding("retailer_01", 10e6, "expand", 2.0)
    assert banking.term_debt("retailer_01") == pytest.approx(10e6)


def test_high_policy_rate_dampens_investment():
    runner = _runner(preference_base=0.0, preference_risk=0.0)
    env, rt = runner.env, _firm(runner, cash=500e6)
    env.central_bank.policy_rate = 0.02
    calm = sum(env.arrange_funding("retailer_01", 1e6, "expand", 2.0) for _ in range(200))
    env.central_bank.policy_rate = 0.06
    tight = sum(env.arrange_funding("retailer_01", 1e6, "expand", 2.0) for _ in range(200))
    assert calm == 200
    assert tight < calm * 0.8


def test_deposit_rates_follow_policy_rate():
    runner = _runner()
    env = runner.env
    runner.config.banking.enabled = False
    env.banking = None
    rt = env.runtimes["retailer_01"]
    rt.last_year_revenue = 0.0
    results = {}
    for policy in (0.0, 0.01, 0.03):
        env.central_bank.policy_rate = policy
        rt.cash, rt.interest_cost, rt.negative_interest_cost = 200e6, 0.0, 0.0
        env._apply_interest(rt)
        results[policy] = (-(rt.interest_cost - rt.negative_interest_cost), rt.negative_interest_cost)
    # Below the threshold a small positive rate is paid, even at a policy rate of zero.
    assert results[0.0][0] > 0
    assert results[0.03][0] > results[0.01][0] > results[0.0][0]
    # The negative rate on the excess rises with the policy rate.
    assert results[0.03][1] > results[0.01][1] >= results[0.0][1] > 0


def test_bank_tab_has_loan_charts():
    from market_sim import dashboard

    for canvas in ("ba-loans", "ba-new", "ba-defaults", "ba-interest", "ba-deposit"):
        assert f'id="{canvas}"' in dashboard._HTML
    assert "renderBankLoans" in dashboard._HTML
