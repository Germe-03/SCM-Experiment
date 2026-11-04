"""Money flow per firm and year: payments per supplier and cash flows with a reason."""

import pytest

from market_sim.run import build_runner


@pytest.fixture(scope="module")
def result():
    runner, _ = build_runner(3, 0, days_per_year=40)
    return runner, runner.run(3)


def test_payments_per_recipient_add_up_to_purchase_cost(result):
    runner, res = result
    for firm_id, rows in res.financial_breakdown.items():
        for row in rows:
            if "paid_to" not in row:  # placeholder years before a firm entered
                continue
            assert sum(row["paid_to"].values()) == pytest.approx(row["purchase_cost"], abs=1.0, rel=1e-6)
            for recipient in row["paid_to"]:
                assert recipient in runner.env.runtimes or recipient == "rohstoffe" or recipient.startswith("staat:")


def test_taxes_are_booked_in_the_year_they_belong_to(result):
    _, res = result
    first_year = [rows[0].get("cash_flows", {}) for rows in res.financial_breakdown.values() if rows]
    assert any("staat:Gewinnsteuer" in flows for flows in first_year)
    assert all(v < 0 for flows in first_year for k, v in flows.items() if k.startswith("staat:"))


def test_only_willing_firms_commit_offences():
    runner, _ = build_runner(2, 0, days_per_year=20)
    runner.config.state.willing_share = 0.0
    runner.run(2)
    assert runner.state_actor.stats["offences"] == 0
