"""Commercial bank accounts, accruals, exits and deterministic continuation."""

import csv
from dataclasses import asdict
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from market_sim.banking import BankingSystem
from market_sim.checkpoint import load_checkpoint, save_checkpoint
from market_sim.config import BankConfig, BankingConfig, load_market_config
from market_sim.run import build_runner, write_outputs


def runtimes(count=10):
    return {f"firm_{i:02}": SimpleNamespace(initial_cash=1000, cash=1000,
            last_year_revenue=0, active=True) for i in range(count)}


def test_year_end_customer_roles_revenue_and_market_shares():
    firms = runtimes(4)
    banking = BankingSystem(BankingConfig(enabled=True, entry_enabled=False,
                            second_account_enabled=False, payout_ratio=0), 42, firms)
    ids = list(banking.banks)
    banking.accounts = {
        'firm_00': {ids[0]: 0.3, ids[1]: 0.7},
        'firm_01': {ids[1]: 1.0},
        'firm_02': {ids[0]: 1.0},
        'firm_03': {ids[1]: 0.5, ids[0]: 0.5},
    }
    firms['firm_02'].cash = -100
    firms['firm_03'].cash = -300
    banking.banks[ids[0]].interest_income = 20
    banking.banks[ids[0]].fee_income = 5
    reports = banking.year_end(firms, BankConfig(), 1, 1, 365, [])
    by_id = {r.bank_id: r for r in reports}
    first, second = by_id[ids[0]], by_id[ids[1]]
    assert first.customer_ids == ['firm_00', 'firm_02', 'firm_03']
    assert first.customers == 3
    assert first.house_customer_ids == ['firm_00', 'firm_02']
    assert first.house_customers == 2
    assert second.house_customer_ids == ['firm_01', 'firm_03']
    assert second.house_customers == 2
    assert first.deposit_share == pytest.approx(300 / 2000)
    assert second.deposit_share == pytest.approx(1700 / 2000)
    assert first.loan_share == pytest.approx(0.25)
    assert second.loan_share == pytest.approx(0.75)
    assert first.revenue == 25
    assert sum(r.deposit_share for r in reports if r.active) == pytest.approx(1)
    assert sum(r.loan_share for r in reports if r.active) == pytest.approx(1)
    for rt in firms.values():
        rt.cash = 0
    empty_reports = banking.year_end(firms, BankConfig(), 1, 2, 365, [])
    assert all(r.deposit_share == r.loan_share == 0 for r in empty_reports)


def test_assignment_balanced_deterministic_and_initial_equity():
    cfg = BankingConfig(enabled=True)
    firms = runtimes()
    first = BankingSystem(cfg, 42, firms)
    second = BankingSystem(cfg, 42, dict(reversed(list(firms.items()))))
    assert first.accounts == second.accounts
    counts = [sum(bid in a for a in first.accounts.values()) for bid in first.banks]
    assert max(counts) - min(counts) <= 1
    assert sum(b.equity for b in first.banks.values()) == 1500
    assert first.accounts != BankingSystem(cfg, 43, firms).accounts
    before = first._rng.getstate()
    first.add_firm("firm_00")
    assert first._rng.getstate() == before
    first.add_firm("entrant")
    assert len(first.accounts["entrant"]) == 1


def test_second_accounts_shares_primary_and_fixed_draws():
    cfg = BankingConfig(enabled=True, second_account_share=0.7, random_weight=0)
    firms = runtimes()
    banking = BankingSystem(cfg, 8, firms)
    other = BankingSystem(cfg, 8, firms)
    primary = {fid: banking.primary_bank(fid).id for fid in firms}
    events = []
    banking.open_second_accounts(firms, BankConfig(deposit_threshold_min=0), 1, 1, 365, events)
    other.open_second_accounts(firms, BankConfig(), 1, 1, 365, [])
    assert banking._rng.getstate() == other._rng.getstate()
    banking.open_second_accounts(firms, BankConfig(deposit_threshold_min=0), 1, 2, 365, events)
    assert len(events) == len(firms)
    for fid, shares in banking.accounts.items():
        assert len(shares) == 2
        assert sum(shares.values()) == pytest.approx(1)
        assert banking.primary_bank(fid).id == primary[fid]
        assert shares[primary[fid]] == pytest.approx(0.3)
        assert events[0]["event"] == "account_opened"
    # Debt stays entirely with the primary bank despite a larger second share.
    for rt in firms.values():
        rt.cash = -100
    banking.aggregate(firms)
    for bid, bank in banking.banks.items():
        assert bank.loans == 100 * sum(p == bid for p in primary.values())
        assert bank.deposits == 0


@pytest.mark.parametrize("enabled,max_accounts", [(False, 2), (True, 1)])
def test_second_account_switches(enabled, max_accounts):
    firms = runtimes()
    banking = BankingSystem(BankingConfig(second_account_enabled=enabled, max_accounts=max_accounts), 0, firms)
    banking.open_second_accounts(firms, BankConfig(deposit_threshold_min=0), 1, 1, 365, [])
    assert all(len(a) == 1 for a in banking.accounts.values())


def test_weak_primary_opens_second_account_below_deposit_threshold():
    firms = runtimes(1)
    banking = BankingSystem(BankingConfig(), 0, firms)
    banking.primary_bank("firm_00").equity = -1
    events = []
    banking.open_second_accounts(firms, BankConfig(), 1, 1, 365, events)
    assert len(banking.accounts["firm_00"]) == 2
    assert len(events) == 1


@pytest.mark.parametrize("central_enabled", [False, True])
def test_debt_interest_matches_bank_income(central_enabled):
    runner, _ = build_runner(days_per_year=2)
    runner.config.central_bank.enabled = central_enabled
    runner.start()
    env = runner.env
    cfg = runner.config.bank
    for fid, rt in env.runtimes.items():
        rt.cash, rt.last_year_revenue = -1000, 2000
        expected_rate = ((env.central_bank.policy_rate if central_enabled else cfg.base_rate)
                         + env.banking.primary_bank(fid).margin + cfg.leverage_premium * 0.5)
        env._apply_interest(rt)
        assert rt.interest_cost == pytest.approx(1000 * min(cfg.max_rate, expected_rate) / 365)
    assert sum(rt.interest_cost for rt in env.runtimes.values()) == pytest.approx(
        sum(b.interest_income for b in env.banking.banks.values()))


def test_deposit_interest_gross_components_follow_shares():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    env = runner.env
    fid = "retailer_01"
    primary = env.banking.primary_bank(fid).id
    second = next(bid for bid in env.banking.banks if bid != primary)
    env.banking.accounts[fid] = {primary: 0.3, second: 0.7}
    rt = env.runtimes[fid]
    rt.cash, rt.last_year_revenue = 100e6, 0
    env._apply_interest(rt)
    for bid, share in env.banking.accounts[fid].items():
        bank = env.banking.banks[bid]
        assert bank.interest_income == pytest.approx(rt.negative_interest_cost * share)
        assert bank.interest_expense == pytest.approx(50e6 * 0.005 / 365 * share)
    assert sum(b.interest_income - b.interest_expense for b in env.banking.banks.values()) == pytest.approx(rt.interest_cost)


@pytest.mark.parametrize("rate", [-0.01, 0.04])
@pytest.mark.parametrize("cash", [-2000, 1000])
def test_daily_refinancing_and_year_end_profit(rate, cash):
    firms = runtimes(1)
    firms["firm_00"].cash = cash
    cfg = BankingConfig(payout_ratio=0, second_account_enabled=False)
    banking = BankingSystem(cfg, 0, firms)
    bank = banking.primary_bank("firm_00")
    equity = bank.equity
    banking.daily(firms, rate)
    expected = (max(0, -cash) - max(0, cash) - equity) * rate / 365
    assert bank.refinancing_cost == pytest.approx(expected)
    assert bank.operating_cost == pytest.approx(abs(cash) * cfg.operating_cost_rate / 365)
    bank.interest_income, bank.interest_expense, bank.write_offs = 10, 2, 3
    reports = banking.year_end(firms, BankConfig(), 1, 1, 365, [])
    report = next(r for r in reports if r.bank_id == bank.id)
    assert report.profit == pytest.approx(10 - 2 - expected - report.operating_cost - 3)
    assert bank.equity == pytest.approx(equity + report.profit)
    assert bank.year_profit == report.profit
    assert bank.write_offs == bank.interest_income == bank.refinancing_cost == 0


def test_payout_keeps_target_capital_and_is_logged():
    firms = runtimes(1)
    firms["firm_00"].cash = -1000
    banking = BankingSystem(BankingConfig(payout_ratio=1, second_account_enabled=False), 0, firms)
    bank = banking.primary_bank("firm_00")
    bank.interest_income = 200
    events = []
    banking.year_end(firms, BankConfig(), 1, 1, 365, events)
    assert bank.equity == 150
    assert bank.capital_ratio == 0.15
    assert len(events) == 1 and events[0]["event"] == "bank_payout"
    assert firms["firm_00"].cash == -1000


@pytest.mark.parametrize("restructure", [False, True])
def test_bankruptcy_write_off_exactly_once(restructure):
    runner, _ = build_runner(days_per_year=2)
    runner.config.bankruptcy.min_firms_per_stage = 1000 if restructure else 0
    runner.config.bankruptcy.min_years_before_exit = 0
    runner.config.bank.restructuring = True
    runner.config.banking.loss_given_default = 1.0
    runner.start()
    fid = "retailer_01"
    rt = runner.env.runtimes[fid]
    bank = runner.env.banking.primary_bank(fid)
    rt.cash, rt.credit_limit = -1000, 1
    runner._apply_bankruptcy(5, [])
    assert bank.write_offs == 1000
    runner._apply_bankruptcy(5, [])
    assert bank.write_offs == 1000
    if restructure:
        assert rt.cash == 0 and rt.active
        assert rt.cash_flows["bank:Schuldenschnitt"] == 1000
    else:
        assert fid not in runner.env.banking.accounts
        runner.env.close_firm(fid)
        assert bank.write_offs == 1000


def test_immediate_exit_and_entry_accounts():
    runner, _ = build_runner(days_per_year=2)
    state = runner.start()
    fid = "retailer_01"
    bank = runner.env.banking.primary_bank(fid)
    runner.env.runtimes[fid].cash = -123
    runner.close_firm_now(fid, 1, state, "poisoning", "Test")
    runner.close_firm_now(fid, 1, state, "poisoning", "Test")
    # Only the loss given default is written off; the rest comes from the bankrupt estate.
    assert bank.write_offs == pytest.approx(123 * runner.config.banking.loss_given_default)
    assert fid not in runner.env.banking.accounts
    firm = runner.network.firm(fid).model_copy(deep=True, update={"id": "new_retailer"})
    runner.env.add_firm(firm)
    assert len(runner.env.banking.accounts[firm.id]) == 1


def test_disabled_matches_missing_config_and_preserves_rng():
    cfg = load_market_config()
    cfg.banking.enabled = False
    legacy = cfg.model_dump()
    del legacy["banking"]
    copied = type(cfg).model_validate(legacy)
    cfg.banking.banks[0].margin = 1
    cfg.banking.start_equity_fraction = 10
    first, _ = build_runner(2, 7, 3, cfg)
    second, _ = build_runner(2, 7, 3, copied)
    a, b = first.run(2), second.run(2)
    assert first.env.banking is second.env.banking is None
    assert a.bank_history == b.bank_history == []
    assert a.final_result == b.final_result
    assert a.system_kpis == b.system_kpis
    assert a.events == b.events
    assert a.annual_reports == b.annual_reports
    assert a.financial_breakdown == b.financial_breakdown
    assert first.demand._rng.getstate() == second.demand._rng.getstate()
    assert first.long_run.rng.getstate() == second.long_run.rng.getstate()
    assert first._phase1_rng.getstate() == second._phase1_rng.getstate()


def test_short_run_csv_and_checkpoint(tmp_path):
    runner, _ = build_runner(2, 4, 3)
    state = runner.start()
    runner.continue_run(state, 1)
    path = save_checkpoint(runner, state, tmp_path / "banking.pkl")
    restored, saved_state = load_checkpoint(path)
    assert restored.env.banking.accounts == runner.env.banking.accounts
    assert restored.env.banking._rng.getstate() == runner.env.banking._rng.getstate()
    assert {bid: asdict(b) for bid, b in restored.env.banking.banks.items()} == {
        bid: asdict(b) for bid, b in runner.env.banking.banks.items()}
    a, b = runner.continue_run(state, 2), restored.continue_run(saved_state, 2)
    assert a.bank_history == b.bank_history
    assert a.events == b.events
    assert a.final_result == b.final_result
    assert a.system_kpis == b.system_kpis
    assert len(a.bank_history) == 6
    for year, kpi in enumerate(a.system_kpis, 1):
        reports = [r for r in a.bank_history if r.year == year]
        assert kpi.total_loans == pytest.approx(sum(r.loans for r in reports))
        assert kpi.total_deposits == pytest.approx(sum(r.deposits for r in reports))
        assert kpi.bank_equity == pytest.approx(sum(r.equity for r in reports))
    paths = write_outputs(a, tmp_path)
    assert tmp_path / "bank_reports.csv" in paths
    with (tmp_path / "bank_reports.csv").open(encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 6
    assert set(rows[0]) == set(a.bank_history[0].model_dump())
    assert rows[0]['customer_ids'] == ';'.join(a.bank_history[0].customer_ids)


@pytest.mark.parametrize("values", [{"banks": []}, {"max_accounts": 3}, {"second_account_share": 1},
                                    {"banks": [{"id": "B1", "name": "a"}, {"id": "B1", "name": "b"}]}])
def test_config_validation(values):
    assert not BankingConfig().enabled
    assert load_market_config().banking.enabled
    with pytest.raises(ValidationError):
        BankingConfig(**values)
