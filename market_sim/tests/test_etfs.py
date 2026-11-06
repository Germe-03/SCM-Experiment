"""Phase 23: ETFs per region, category and stage (display only, chain-linked)."""

import types

import pytest

from market_sim.stock_market import EtfBook


def cfg(**kw):
    base = dict(
        etfs_enabled=True,
        etf_groups=["region", "category", "stage"],
        etf_weighting="market_cap",
        etf_base=100.0,
        shares_per_firm=1_000_000,
        etf_min_members=1,
        etf_min_price=0.0,
        etf_max_weight=1.0,
    )
    base.update(kw)
    return types.SimpleNamespace(**base)


def firm(stage="factory", region="bern", category="beer", channel="store"):
    return types.SimpleNamespace(
        stage=stage, region=region, category=category, channel=channel
    )


def test_groups_and_members():
    members = {
        "factory": firm(),
        "restaurant": firm(stage="retailer", region="zuerich", channel="restaurant"),
        "wholesaler": firm(stage="wholesaler"),
    }
    book = EtfBook(cfg())

    book.update(members, {firm_id: 10.0 for firm_id in members}, 1, 1, 0)

    assert book.definitions["region:bern"]["members"] == ["factory", "wholesaler"]
    assert book.definitions["region:zuerich"]["members"] == ["restaurant"]
    assert book.definitions["category:beer"]["members"] == ["factory"]
    assert book.definitions["stage:restaurant"]["members"] == ["restaurant"]
    assert book.definitions["stage:wholesaler"]["members"] == ["wholesaler"]
    assert [etf_id for etf_id in book.definitions if etf_id.startswith("category:")] == [
        "category:beer"
    ]
    assert all(level == 100.0 for level in book.rows[0].values() if isinstance(level, float))


def test_only_selected_groups():
    book = EtfBook(cfg(etf_groups=["stage"]))

    book.update({"a": firm()}, {"a": 10.0}, 1, 1, 0)

    assert book.definitions
    assert all(etf_id.startswith("stage:") for etf_id in book.definitions)


def test_market_cap_chain_link():
    book = EtfBook(cfg())
    members = {"a": firm(), "b": firm()}

    book.update(members, {"a": 10.0, "b": 30.0}, 1, 1, 0)
    book.update(members, {"a": 20.0, "b": 30.0}, 2, 1, 1)

    assert book.rows[1]["category:beer"] == pytest.approx(125.0)


def test_equal_weighting():
    book = EtfBook(cfg(etf_weighting="equal"))
    members = {"a": firm(), "b": firm()}

    book.update(members, {"a": 10.0, "b": 30.0}, 1, 1, 0)
    book.update(members, {"a": 20.0, "b": 30.0}, 2, 1, 1)

    assert book.rows[1]["category:beer"] == pytest.approx(150.0)


def test_no_jump_on_listing_and_exit():
    book = EtfBook(cfg())
    a = firm()
    b = firm()

    book.update({"a": a}, {"a": 10.0}, 1, 1, 0)
    book.update({"a": a, "b": b}, {"a": 10.0, "b": 1000.0}, 2, 1, 1)
    assert book.rows[1]["category:beer"] == pytest.approx(100.0)

    book.update({"a": a, "b": b}, {"a": 12.0, "b": 1000.0}, 3, 1, 2)
    day3_level = book.rows[2]["category:beer"]
    assert day3_level == pytest.approx(100.0 * (1012.0 / 1010.0))

    book.update({"b": b}, {"b": 1000.0}, 4, 1, 3)
    assert book.rows[3]["category:beer"] == pytest.approx(day3_level)


def test_empty_etf_has_no_price():
    book = EtfBook(cfg())
    a = firm(region="bern")
    c = firm(region="tessin")

    book.update({"a": a}, {"a": 10.0}, 1, 1, 0)
    last_level = book.rows[0]["region:bern"]
    book.update({"c": c}, {"c": 20.0}, 2, 1, 1)

    assert "region:bern" not in book.rows[1]
    assert len(book.rows) == 2

    book.update({"a": a}, {"a": 50.0}, 3, 1, 2)
    assert book.rows[2]["region:bern"] == pytest.approx(last_level)


def test_weights():
    market_cap_book = EtfBook(cfg())
    members = {"a": firm(), "b": firm()}
    prices = {"a": 10.0, "b": 30.0}
    market_cap_book.update(members, prices, 1, 1, 0)

    assert market_cap_book.weights("category:beer", prices) == pytest.approx(
        {"a": 0.25, "b": 0.75}
    )
    assert market_cap_book.weights("unknown", prices) == {}

    equal_book = EtfBook(cfg(etf_weighting="equal"))
    equal_book.update(members, prices, 1, 1, 0)
    assert equal_book.weights("category:beer", prices) == pytest.approx(
        {"a": 0.5, "b": 0.5}
    )


def test_deterministic_and_aligned_in_simulation():
    from market_sim.run import build_runner

    rows = []
    definitions = []
    daily_row_counts = []

    for _ in range(2):
        runner, _ = build_runner(days_per_year=4)
        runner.config.stock_market.tradable_from_year = 1
        state = runner.start()
        sm = runner.stock_market

        for day in range(20):
            sm.daily(runner, state, 1, day, day)

        rows.append(sm.etfs.rows)
        definitions.append(sm.etfs.definitions)
        daily_row_counts.append(len(sm.daily_rows))

    assert rows[0] == rows[1]
    assert len(rows[0]) == daily_row_counts[0]
    assert len(rows[1]) == daily_row_counts[1]
    assert any(etf_id.startswith("region:") for etf_id in definitions[0])
    assert any(etf_id.startswith("stage:") for etf_id in definitions[0])


def test_disabled():
    from market_sim.run import build_runner
    from market_sim.stock_market import StockMarket

    runner, _ = build_runner(days_per_year=4)
    runner.config.stock_market.etfs_enabled = False

    assert StockMarket(runner, 0).etfs is None


def test_dashboard_export():
    from market_sim.dashboard_data import _etf_weekly, _stock_weekly

    stock_rows = [
        {
            "global_day": day,
            "year": 1 if day < 5 else 2,
            "day": day,
            "index": 1000.0,
        }
        for day in range(10)
    ]
    etf_rows = [
        {"region:bern": 100.0 + day} if day != 3 else {}
        for day in range(10)
    ]
    definitions = [
        {
            "id": "region:bern",
            "kind": "region",
            "key": "bern",
            "members": ["a"],
        }
    ]

    result = _etf_weekly(stock_rows, etf_rows, definitions, "market_cap")

    assert result["weighting"] == "market_cap"
    assert result["definitions"] == definitions
    assert len(result["levels"]["region:bern"]) == len(_stock_weekly(stock_rows)["days"])
    assert _etf_weekly(stock_rows, etf_rows[:-1], definitions, "market_cap") is None
    assert _etf_weekly(stock_rows, etf_rows, [], "market_cap") is None


def test_branche_group_enables_stage_indices_without_duplicates():
    members = {"f": firm(), "r": firm(stage="retailer", channel="restaurant")}
    book = EtfBook(cfg(etf_groups=["branche"]))

    book.update(members, {"f": 10.0, "r": 10.0}, 1, 1, 0)

    assert sorted(book.definitions) == ["stage:factory", "stage:restaurant"]


def test_etf_needs_min_members():
    book = EtfBook(cfg(etf_min_members=3, etf_min_price=1.0, etf_max_weight=0.30))
    members = {"a": firm(), "b": firm()}

    book.update(members, {"a": 10.0, "b": 10.0}, 1, 1, 0)
    assert "category:beer" not in book.rows[0]

    members["c"] = firm()
    book.update(members, {"a": 10.0, "b": 10.0, "c": 10.0}, 2, 1, 1)
    assert book.rows[1]["category:beer"] == pytest.approx(100.0)


def test_below_min_price_does_not_count():
    book = EtfBook(cfg(etf_min_members=3, etf_min_price=1.0, etf_max_weight=0.30))
    members = {"a": firm(), "b": firm(), "c": firm()}

    book.update(members, {"a": 10.0, "b": 10.0, "c": 0.5}, 1, 1, 0)
    assert "category:beer" not in book.rows[0]

    book.update(members, {"a": 10.0, "b": 10.0, "c": 1.0}, 2, 1, 1)
    assert "category:beer" in book.rows[1]


def test_weight_cap_30_percent():
    book = EtfBook(cfg(etf_min_members=3, etf_min_price=1.0, etf_max_weight=0.30))
    members = {"a": firm(), "b": firm(), "c": firm(), "d": firm()}
    prices = {"a": 100.0, "b": 1.0, "c": 1.0, "d": 1.0}

    book.update(members, prices, 1, 1, 0)
    weights = book.weights("category:beer", prices)

    assert weights["a"] == pytest.approx(0.30)
    assert weights["b"] == pytest.approx(0.70 / 3)
    assert weights["c"] == pytest.approx(0.70 / 3)
    assert weights["d"] == pytest.approx(0.70 / 3)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_small_etf_equal_weights_when_cap_infeasible():
    book = EtfBook(cfg(etf_min_members=3, etf_min_price=1.0, etf_max_weight=0.30))
    members = {"a": firm(), "b": firm(), "c": firm()}
    prices = {"a": 10.0, "b": 20.0, "c": 30.0}

    book.update(members, prices, 1, 1, 0)
    weights = book.weights("category:beer", prices)

    assert weights == pytest.approx({"a": 1 / 3, "b": 1 / 3, "c": 1 / 3})
    assert sum(weights.values()) == pytest.approx(1.0)


def test_gap_then_revival_no_jump():
    book = EtfBook(cfg(etf_min_members=3, etf_min_price=1.0, etf_max_weight=0.30))
    members = {"a": firm(), "b": firm(), "c": firm()}

    book.update(members, {"a": 10.0, "b": 10.0, "c": 10.0}, 1, 1, 0)
    assert book.rows[0]["category:beer"] == 100.0

    book.update({"a": members["a"], "b": members["b"]}, {"a": 10.0, "b": 10.0}, 2, 1, 1)
    assert "category:beer" not in book.rows[1]

    book.update(members, {"a": 20.0, "b": 20.0, "c": 20.0}, 3, 1, 2)
    assert book.rows[2]["category:beer"] == pytest.approx(100.0)

    book.update(members, {"a": 30.0, "b": 30.0, "c": 30.0}, 4, 1, 3)
    assert book.rows[3]["category:beer"] == pytest.approx(150.0)


def test_weights_respect_min_price():
    book = EtfBook(cfg(etf_min_members=3, etf_min_price=1.0, etf_max_weight=0.30))
    members = {"a": firm(), "b": firm(), "c": firm()}
    prices = {"a": 10.0, "b": 10.0, "c": 0.5}

    book.update(members, prices, 1, 1, 0)

    assert book.weights("category:beer", prices) == {}


def test_dashboard_export_applies_etf_rules():
    from market_sim.dashboard_data import _etf_weekly, _weekly_selection

    stock_cfg = cfg(
        etf_min_members=3,
        etf_min_price=1.0,
        etf_max_weight=0.30,
        etf_weighting="market_cap",
    )
    stock_rows = []
    for day in range(15):
        row = {
            "global_day": day,
            "year": 1 if day < 10 else 2,
            "day": day,
            "index": 1000.0,
            "a": 100.0,
            "b": 1.0,
            "c": 1.0,
            "d": 0.5 if day == 6 else 1.0,
        }
        stock_rows.append(row)

    etf_rows = [{} for _ in stock_rows]
    definitions = [
        {
            "id": "category:beer",
            "kind": "category",
            "key": "beer",
            "members": ["a", "b", "c", "d"],
        }
    ]

    result = _etf_weekly(
        stock_rows, etf_rows, definitions, "market_cap", stock_cfg
    )
    selected = _weekly_selection(stock_rows)

    assert result["config"] == {
        "min_price": 1.0,
        "min_members": 3,
        "max_weight": 0.30,
    }
    assert stock_rows[selected[0]]["day"] == 6
    assert result["members"]["category:beer"][0] == 3

    first_weights = result["weights"]["category:beer"][0]
    assert len(first_weights) == 3
    assert sum(weight for _, weight in first_weights) == pytest.approx(
        1.0, abs=2e-6
    )

    full_member_index = next(
        index for index, day_index in enumerate(selected)
        if result["members"]["category:beer"][index] == 4
    )
    full_weights = result["weights"]["category:beer"][full_member_index]
    assert dict(full_weights)["a"] == pytest.approx(0.30)
    assert len(full_weights) == 4
    assert sum(weight for _, weight in full_weights) == pytest.approx(
        1.0, abs=2e-6
    )

    result_without_cfg = _etf_weekly(
        stock_rows, etf_rows, definitions, "market_cap"
    )
    assert "members" not in result_without_cfg
    assert "weights" not in result_without_cfg
