"""Wine entrants: start cash for maturation, grace period, cooldown after failure."""

from market_sim.run import build_runner


def test_config_defaults():
    runner, _ = build_runner(years=1, days_per_year=2)
    cfg = runner.config.market_entry
    assert cfg.forced_entry_cooldown_years >= 0
    assert cfg.maturation_start_cash_factor >= 0
    assert cfg.maturation_grace_years >= 0


def test_in_maturation_until_first_sale():
    runner, _ = build_runner(years=1, days_per_year=2)
    runner.config.market_entry.maturation_grace_years = 2
    runner._entry_year["x"] = 5
    assert runner._in_maturation("x", 6)
    assert not runner._in_maturation("x", 7)
    runner._first_sale_year["x"] = 6
    assert not runner._in_maturation("x", 6)
    assert not runner._in_maturation("unknown", 6)
