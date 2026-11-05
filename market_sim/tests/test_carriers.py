"""Phase 28: the Post replaces the anonymous transport service."""

import pytest

from market_sim.config import load_market_config
from market_sim.run import build_runner, write_outputs


def _config(enabled=True, couriers=False, **post):
    config = load_market_config()
    carriers = config.carriers.model_copy(update={
        "enabled": enabled, "post": config.carriers.post.model_copy(update=post),
        "couriers": config.carriers.couriers.model_copy(update={"enabled": couriers})})
    return config.model_copy(update={"carriers": carriers})


def _run(config, years=2, days=30, seed=0):
    runner, run_years = build_runner(years, seed, days_per_year=days, config=config)
    return runner, runner.run(run_years)


def test_disabled_by_default_and_no_carrier_market():
    config = load_market_config()
    assert config.carriers.enabled is False

    runner, result = _run(config, years=1)

    assert runner.env.geography.carriers is None
    assert result.carriers == []


def test_post_with_old_numbers_gives_identical_results():
    _, a = _run(_config(enabled=False), years=2, days=30, seed=3)
    _, b = _run(
        _config(enabled=True, max_tariff_step=0.0, capacity_per_day=0.0),
        years=2,
        days=30,
        seed=3,
    )

    assert [k.model_dump() for k in a.system_kpis] == [
        k.model_dump() for k in b.system_kpis
    ]
    for a_reports, b_reports in zip(a.annual_reports, b.annual_reports):
        assert {
            fid: report.model_dump() for fid, report in a_reports.items()
        } == {
            fid: report.model_dump() for fid, report in b_reports.items()
        }
    assert a.events == [event for event in b.events if event["firm"] != "post"]

    post_rows = [row for row in b.carriers if row["carrier"] == "post"]
    assert post_rows
    assert all(row["tariff"] == 1.4 for row in post_rows)
    assert sum(row["units"] for row in b.carriers) > 0


def test_post_loss_is_covered_by_bundesbeitrag_and_never_bankrupt():
    runner, result = _run(
        _config(fixed_cost_per_day=1e9, max_tariff_step=0.05, capacity_per_day=0.0),
        years=2,
        days=30,
    )

    for row in result.carriers:
        assert row["bundesbeitrag"] > 0
        assert row["profit"] < 0
        assert row["bundesbeitrag"] == pytest.approx(
            -row["profit"], rel=1e-6, abs=1.0
        )
        assert row["cash"] >= 0
    assert any(
        event["event"] == "bundesbeitrag" and event["firm"] == "post"
        for event in result.events
    )
    assert "post" not in runner.exits


def test_uniform_tariff_moves_at_most_five_percent_per_year():
    _, result = _run(
        _config(fixed_cost_per_day=1e9, max_tariff_step=0.05, capacity_per_day=0.0),
        years=3,
        days=30,
    )

    rows = [row for row in result.carriers if row["carrier"] == "post"]
    rows_with_traffic = [row for row in rows if row["units"] > 0]
    assert rows_with_traffic
    for row in rows_with_traffic:
        assert row["next_tariff"] == pytest.approx(
            row["tariff"] * 1.05, rel=1e-3
        )
    for index in range(len(rows) - 1):
        assert rows[index + 1]["tariff"] == pytest.approx(
            rows[index]["next_tariff"], rel=1e-3
        )

    runner, _ = build_runner(
        1,
        0,
        days_per_year=10,
        config=_config(capacity_per_day=0.0),
    )
    runner.start()
    geo = runner.env.geography
    supplier = runner.network.firm("wholesaler_01")
    customer = runner.network.firm("retailer_01")
    supplier.transport_mode = "service"
    assert geo.carriers.rate(supplier, customer) == geo.carriers.post.tariff

    supplier = runner.network.firm("distributor_01")
    customer = runner.network.firm("wholesaler_01")
    supplier.transport_mode = "service"
    assert geo.carriers.rate(supplier, customer) == geo.carriers.post.tariff


def test_overload_delays_parcels_and_nothing_is_lost():
    runner, _ = build_runner(
        1,
        0,
        days_per_year=10,
        config=_config(capacity_per_day=10.0),
    )
    runner.start()
    env = runner.env
    market = env.geography.carriers
    supplier = runner.network.firm("wholesaler_01")
    customer = runner.network.firm("retailer_01")

    delays = [
        market.book(env.period, supplier, customer, 6, 50.0, 100.0, 1.0)
        for _ in range(4)
    ]

    assert delays == [0, 1, 1, 2]
    assert market.post.delayed_units == 18

    before = sum(env.runtimes["retailer_01"].incoming_shipments)
    market.hold(env.period + 2, "retailer_01", {"x": 5}, 5)
    market.release(env)
    assert sum(env.runtimes["retailer_01"].incoming_shipments) == before
    assert market.held_units() == 5

    env.period += 2
    market.release(env)
    assert sum(env.runtimes["retailer_01"].incoming_shipments) == before + 5
    assert env.runtimes["retailer_01"].incoming_brands[-1].get("x") == 5
    assert market.held_units() == 0
    assert market.lost_units == 0

    market.daily(env)
    assert market.post.waiting_units == pytest.approx(14.0)
    assert market.post.busy_days == 1


def test_tiny_capacity_in_a_run_gives_delays_and_post_expands():
    _, result = _run(
        _config(capacity_per_day=5.0, max_tariff_step=0.0),
        years=2,
        days=30,
        seed=0,
    )

    assert any(
        row["delayed_units"] > 0 and row["mean_delay_days"] > 0
        for row in result.carriers
    )
    assert any(event["event"] == "post_capacity" for event in result.events)


def test_carrier_report_csv_is_written(tmp_path):
    _, result = _run(
        _config(enabled=True, max_tariff_step=0.0, capacity_per_day=0.0),
        years=1,
        days=30,
        seed=3,
    )

    write_outputs(result, tmp_path)

    report = tmp_path / "carrier_report.csv"
    assert report.exists()
    first_line = report.read_text().splitlines()[0]
    assert "bundesbeitrag" in first_line
    assert "tariff" in first_line
