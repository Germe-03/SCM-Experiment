"""Policy rule, monetary transmission and deterministic continuation."""

import csv

import pytest
from pydantic import ValidationError

from market_sim.banking import CentralBank
from market_sim.checkpoint import load_checkpoint, save_checkpoint
from market_sim.config import CentralBankConfig, load_market_config
from market_sim.run import build_runner, write_outputs


def bank(**kwargs):
    return CentralBank(CentralBankConfig(enabled=True, **kwargs))


def test_rule_inflation_step_and_rounding():
    low, high = bank(), bank()
    low.year_end(0.01, 100, 100)
    high.year_end(0.04, 100, 100)
    assert low.policy_rate == 0.01
    assert high.policy_rate == 0.015
    rounded = bank(max_step=0.08)
    rounded.year_end(0.013, 100, 100)
    assert rounded.policy_rate == 0.015
    assert rounded.policy_rate / 0.0025 == pytest.approx(6)


@pytest.mark.parametrize('inflation,limit', [(1, 0.08), (-1, -0.0075)])
def test_rate_limits_and_steps(inflation, limit):
    cb = bank()
    for _ in range(30):
        previous = cb.policy_rate
        cb.year_end(inflation, 100, 100)
        assert abs(cb.policy_rate - previous) <= 0.005 + 1e-12
    assert cb.policy_rate == limit


def test_gap_smoothing_caps_and_zero_demand():
    cb = bank(demand_effect=100, inflation_effect=100)
    cb.year_end(-1, 1000, 100)
    assert cb.output_gap == pytest.approx(0.05)
    assert cb.demand_multiplier == 0.95
    assert cb.inflation_adjustment == 0.005
    cb.year_end(1, 0, 100)
    assert cb.output_gap == pytest.approx(-0.025)
    assert cb.demand_multiplier == 1.05
    assert cb.inflation_adjustment == -0.005
    cb.year_end(0.01, 0, 0)
    assert cb.output_gap == pytest.approx(-0.0125)


def test_demand_uses_previous_rate():
    cb = bank()
    cb.year_end(0.01, 200, 100)
    assert cb.policy_rate == 0.015
    assert cb.demand_multiplier == 1.0
    cb.year_end(0.01, 100, 100)
    assert cb.demand_multiplier == pytest.approx(0.9975)


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('policy_rate', [-0.01, 0.04])
@pytest.mark.parametrize('cash', [-1000.0, 1000.0, 100e6])
def test_interest_uses_policy_only_when_enabled(enabled, policy_rate, cash):
    runner, _ = build_runner(1, days_per_year=3)
    runner.config.central_bank.enabled = enabled
    runner.config.banking.enabled = False
    runner.env.central_bank.policy_rate = policy_rate
    runner.start()
    rt = runner.env.runtimes['retailer_01']
    rt.cash, rt.last_year_revenue, rt.consecutive_loss_years = cash, 2000, 2
    cfg = runner.config.bank
    base = policy_rate + cfg.loan_margin if enabled else cfg.base_rate
    deposit = max(0, policy_rate - cfg.deposit_spread) if enabled else cfg.deposit_rate
    negative = max(cfg.negative_rate, -policy_rate) if enabled else cfg.negative_rate
    threshold = max(cfg.deposit_threshold_min, cfg.deposit_threshold_revenue_fraction * 2000)
    expected = (-cash * min(cfg.max_rate, base + 2 * cfg.risk_premium_per_loss_year
                           + cfg.leverage_premium * 0.5) / 365 if cash < 0 else
                (max(0, cash - threshold) * negative - min(cash, threshold) * deposit) / 365)
    runner.env._apply_interest(rt)
    assert rt.interest_cost == pytest.approx(expected)
    assert rt.cash == pytest.approx(cash - expected)


def test_config_defaults_and_validation():
    assert not CentralBankConfig().enabled
    assert load_market_config().central_bank.enabled
    with pytest.raises(ValidationError):
        CentralBankConfig(start_rate=0.2)
    with pytest.raises(ValidationError):
        CentralBankConfig(gap_smoothing=1.1)


def test_disabled_preserves_results_and_random_streams():
    first, _ = build_runner(2, days_per_year=3)
    second, _ = build_runner(2, days_per_year=3)
    for runner in (first, second):
        runner.config.central_bank.enabled = False
    second.env.central_bank.policy_rate = 0.08
    second.env.central_bank.output_gap = 0.1
    second.env.central_bank.demand_multiplier = 0.5
    second.config.bank.loan_margin = 1
    second.config.bank.deposit_spread = 1
    a, b = first.run(2), second.run(2)
    assert a.system_kpis == b.system_kpis
    assert a.annual_reports == b.annual_reports
    assert a.events == b.events
    assert first.demand._rng.getstate() == second.demand._rng.getstate()
    assert first.long_run.rng.getstate() == second.long_run.rng.getstate()


def test_higher_rate_lowers_next_inflation_with_same_shocks():
    low, _ = build_runner(3, days_per_year=5)
    high, _ = build_runner(3, days_per_year=5)
    high.env.central_bank.policy_rate = 0.08
    for runner in (low, high):
        runner.config.events.enabled = False
        runner.config.long_run.inflation_sd = 0
    a, b = low.run(3), high.run(3)
    assert b.system_kpis[0].inflation == a.system_kpis[0].inflation
    assert b.system_kpis[2].output_gap < a.system_kpis[2].output_gap
    assert b.system_kpis[2].inflation < a.system_kpis[2].inflation
    assert low.demand._rng.getstate() == high.demand._rng.getstate()


def test_short_run_csv_events_and_checkpoint(tmp_path):
    runner, _ = build_runner(3, days_per_year=3)
    runner.config.long_run.inflation_mean = 0.04
    runner.config.long_run.inflation_sd = 0
    state = runner.start()
    runner.continue_run(state, 1)
    path = save_checkpoint(runner, state, tmp_path / 'snb.pkl')
    restored, restored_state = load_checkpoint(path)
    assert vars(restored.env.central_bank) == vars(runner.env.central_bank)
    straight = runner.continue_run(state, 3)
    resumed = restored.continue_run(restored_state, 3)
    assert straight.system_kpis == resumed.system_kpis
    assert straight.annual_reports == resumed.annual_reports
    assert straight.events == resumed.events
    events = [e for e in straight.events if e['event'] == 'policy_rate_changed']
    assert events and events[0]['firm'] == 'SNB' and events[0]['day'] == 3
    write_outputs(straight, tmp_path)
    with (tmp_path / 'system_kpis.csv').open(encoding='utf-8') as source:
        rows = list(csv.DictReader(source))
    assert len(rows) == 3
    assert float(rows[0]['policy_rate']) == 0.015
    assert float(rows[0]['inflation']) == 0.04
    assert abs(float(rows[0]['output_gap'])) <= 0.1


def test_policy_updates_without_longrun():
    runner, _ = build_runner(1, days_per_year=3)
    runner.config.long_run.enabled = False
    result = runner.run(1)
    assert result.system_kpis[0].inflation == 0
    assert result.system_kpis[0].policy_rate is not None
