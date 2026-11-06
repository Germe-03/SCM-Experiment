"""Bank failure: 30 % deposit insurance, free choice of the next bank, bounded rounds, new banks."""

import pytest

from market_sim.run import build_runner


def test_failed_bank_costs_customers_seventy_percent():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    fid = "retailer_01"
    system.accounts[fid] = {"B1": 1.0}
    rts[fid].cash = 1000.0
    system.banks["B1"].equity = -1
    events = []

    system.resolve_failures(rts, 3, 2, events)

    assert system.banks["B1"].active is False
    assert system.banks["B1"].failed_year == 3
    assert rts[fid].cash == pytest.approx(300.0)
    assert rts[fid].cash_flows["bankpleite:B1"] == pytest.approx(-700.0)
    assert "B1" not in system.accounts[fid]
    assert len(system.accounts[fid]) == 1
    failed = [event for event in events if event["event"] == "bank_failed"]
    assert len(failed) == 1
    assert "year" in failed[0] and "day" in failed[0]
    assert any(event["event"] == "bank_switched" and event["firm"] == fid
               for event in events)


def test_second_account_halves_the_loss():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    fid = "retailer_01"
    system.accounts[fid] = {"B1": 0.5, "B2": 0.5}
    rts[fid].cash = 1000.0
    system.banks["B1"].equity = -1

    system.resolve_failures(rts, 3, 2, [])

    assert rts[fid].cash == pytest.approx(1000 - 500 * 0.7)
    assert system.accounts[fid] == {"B2": 1.0}


def test_customers_choose_banks_freely_not_all_to_strongest():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    for fid in sorted(system.accounts):
        system.accounts[fid] = {"B1": 1.0}
        rts[fid].cash = 1000.0
    system.banks["B2"].equity = system.banks["B3"].equity
    system.banks["B2"].margin = 0.02
    system.banks["B3"].margin = 0.02
    system.cfg.random_weight = 1.0
    system.banks["B1"].equity = -1

    system.resolve_failures(rts, 3, 2, [])

    new_banks = {next(iter(system.accounts[fid])) for fid in system.accounts
                 if "B1" not in system.accounts[fid]}
    assert new_banks == {"B2", "B3"}


def test_debtor_without_accepting_bank_gets_credit_called():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    fid = "retailer_01"
    for other in system.accounts:
        system.accounts[other] = {"B2": 1.0}
    system.accounts[fid] = {"B1": 1.0}
    rts[fid].cash = -1_000_000_000
    system.banks["B2"].equity = 1.0
    system.banks["B3"].equity = 1.0
    system.banks["B1"].equity = -1

    system.resolve_failures(rts, 3, 2, [])

    assert rts[fid].credit_limit == 0
    assert len(system.accounts[fid]) == 1
    assert "B1" not in system.accounts[fid]


def test_rounds_are_bounded_when_all_banks_fail():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    for bank in system.banks.values():
        bank.equity = -1

    system.resolve_failures(rts, 3, 2, [])

    assert all(not bank.active for bank in system.banks.values())
    assert all(system.accounts[fid] == {} for fid in system.accounts)


def test_new_bank_enters_after_failure():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    system.cfg.entry_enabled = True
    system.cfg.entry_probability = 1.0
    system.banks["B1"].equity = -1
    events = []

    system.year_end(rts, runner.config.bank, 1.0, 1, 2, events)

    assert any(event["event"] == "bank_entry" for event in events)
    assert "B4" in system.banks
    assert system.banks["B4"].active
    assert system.banks["B4"].equity == pytest.approx(system.start_equity)


def test_entry_disabled_never_adds_banks():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    system.cfg.entry_enabled = False
    system.banks["B1"].equity = -1

    system.year_end(rts, runner.config.bank, 1.0, 1, 2, [])

    assert len(system.banks) == 3


def test_orphans_join_the_new_bank_and_interest_still_works():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    rts = runner.env.runtimes
    for bank in system.banks.values():
        bank.equity = -1
    system.resolve_failures(rts, 1, 2, [])
    runner.env._apply_interest(rts["retailer_01"], "retailer_01")
    system.cfg.entry_enabled = True
    system.cfg.entry_probability = 1.0
    system.enter_bank(rts, 1.0, 1, 2, [])
    assert all(system.accounts[fid] == {"B4": 1.0} for fid in system.accounts if rts[fid].active)


def _entry_system():
    runner, _ = build_runner(days_per_year=2)
    runner.start()
    system = runner.env.banking
    system.cfg.entry_enabled = True
    system.cfg.entry_probability = 1.0
    system.cfg.entry_min_roe = -1.0
    return system, runner.env.runtimes


def _add_banks(system, count):
    for i in range(count):
        bid = f"X{i}"
        system.banks[bid] = type(system.banks["B1"])(bid, bid, 0.02, 1.0)


def test_phase36_max_five_active_banks():
    system, rts = _entry_system()
    _add_banks(system, 2)
    system.enter_bank(rts, 1.0, 1, 2, [])
    assert sum(b.active for b in system.banks.values()) == 5 and system.cfg.max_banks == 5
    assert len(system.banks) == 5
    system.enter_bank(rts, 1.0, 50, 2, [])
    assert len(system.banks) == 5


def test_phase36_ten_years_between_foundings():
    system, rts = _entry_system()
    system.enter_bank(rts, 1.0, 1, 2, [])
    assert len(system.banks) == 4
    system.enter_bank(rts, 1.0, 5, 2, [])
    assert len(system.banks) == 4
    system.enter_bank(rts, 1.0, 11, 2, [])
    assert len(system.banks) == 5


def test_phase36_waiting_waived_below_three_active():
    system, rts = _entry_system()
    system.enter_bank(rts, 1.0, 1, 2, [])
    system.banks["B1"].active = False
    system.banks["B2"].active = False
    system.enter_bank(rts, 1.0, 2, 2, [])
    assert len(system.banks) == 5
