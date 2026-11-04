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


def test_item_ledgers_match_partner_payments_and_revenue(result):
    runner, res = result
    for firm_id, rows in res.financial_breakdown.items():
        for index, row in enumerate(rows):
            for partner, amount in row.get("paid_to", {}).items():
                items = [v for k, v in row["paid_items"].items() if k.rsplit("|", 1)[0] == partner]
                assert sum(v["chf"] for v in items) == pytest.approx(amount, abs=0.03)
                if partner in runner.env.runtimes:
                    seller = res.financial_breakdown[partner][index]["sold_items"]
                    for key, item in row["paid_items"].items():
                        supplier, category = key.rsplit("|", 1)
                        if supplier == partner:
                            assert seller[f"{firm_id}|{category}"] == item
            assert sum(v["chf"] for v in row.get("sold_items", {}).values()) == pytest.approx(
                row["revenue"], abs=0.2)
        # Snapshots must be independent yearly deltas, not cumulative aliases.
        runtime = runner.env.runtimes[firm_id]
        for key, item in runtime.sold_items.items():
            for metric in ("chf", "units"):
                assert sum(row.get("sold_items", {}).get(key, {}).get(metric, 0) for row in rows) == pytest.approx(
                    item[metric], abs=0.03)


@pytest.mark.parametrize("categories", [True, False])
def test_mixed_parcel_uses_category_value_and_actual_units(categories):
    runner, _ = build_runner(1, 0, days_per_year=2)
    runner.start()
    env = runner.env
    env.brand_book.categories_on = categories
    parcel = {"alpen_lager": 2, "wallis_rot": 1}
    original = dict(parcel)
    items = env.trade_items(parcel, 360)
    assert parcel == original
    if categories:
        assert items == {"beer": {"chf": pytest.approx(200), "units": 2},
                         "wine": {"chf": pytest.approx(160), "units": 1}}
    else:
        assert items == {"alle": {"chf": 360, "units": 3}}
