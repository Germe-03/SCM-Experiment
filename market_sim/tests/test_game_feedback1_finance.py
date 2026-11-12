from types import SimpleNamespace

from market_sim.game import world_finance


def test_stocks_note_when_market_is_not_yet_tradable():
    runner = SimpleNamespace(
        stock_market=SimpleNamespace(
            listed=set(),
            cfg=SimpleNamespace(tradable_from_year=5),
            prices={},
            daily_rows=[],
        )
    )
    state = SimpleNamespace(year=1)

    result = world_finance.stocks(runner, state, "p1")

    assert "Jahr 5" in result["note"]
    assert result["index_history"] == []


def test_stocks_builds_monthly_index_history():
    runner = SimpleNamespace(
        stock_market=SimpleNamespace(
            listed={"f1"},
            cfg=SimpleNamespace(tradable_from_year=1, shares_per_firm=100),
            prices={"f1": 10.0},
            daily_rows=[
                {"year": 1, "day": 1, "index": 100.0, "f1": 10.0},
                {"year": 1, "day": 31, "index": 110.0, "f1": 11.0},
            ],
        ),
        config=SimpleNamespace(
            simulation=SimpleNamespace(days_per_month=30)
        ),
        network=SimpleNamespace(
            firm=lambda firm_id: SimpleNamespace(name="Firma", branch="Brauerei")
        ),
    )
    state = SimpleNamespace(year=1)

    result = world_finance.stocks(runner, state, "p1")

    assert result["note"] is None
    assert [row["label"] for row in result["index_history"]] == [
        "Jahr 1, Monat 1",
        "Jahr 1, Monat 2",
    ]


def _truck_runner(transport_mode="own", personnel_cap=100, annual_cost=10000.0):
    player_id = "p1"
    offer = {
        "type": "t",
        "label": "T",
        "capacity": 50.0,
        "price": 100000.0,
        "annual_cost": annual_cost,
        "life_years": 10,
        "lease_possible": False,
    }
    runner = SimpleNamespace(
        env=SimpleNamespace(
            geography=SimpleNamespace(
                trucks=SimpleNamespace(
                    types={},
                    fleets={},
                    capacity=lambda pid: 3000,
                    REF_KM=100,
                )
            ),
            _effective_capacity=lambda pid: personnel_cap,
            runtimes={
                player_id: SimpleNamespace(revenue=0, purchase_cost=0)
            },
        ),
        config=SimpleNamespace(
            unit_scale=SimpleNamespace(real_units_per_sim_unit=10),
            simulation=SimpleNamespace(days_per_year=360),
        ),
        network=SimpleNamespace(
            firm=lambda pid: SimpleNamespace(
                transport_mode=transport_mode,
                sell_price=2.0,
            )
        ),
    )
    return runner, player_id, offer


def test_trucks_calculates_transport_limited_extra_sales(monkeypatch):
    runner, player_id, offer = _truck_runner()
    state = SimpleNamespace(recent_demand={player_id: [100, 100]})
    monkeypatch.setattr(
        "market_sim.game.actions.truck_offers",
        lambda runner, pid: [offer],
    )

    result = world_finance.trucks(runner, state, player_id)
    truck_offer = result["offers"][0]

    assert truck_offer["extra_sales_per_day"] == 500.0
    assert truck_offer["extra_profit_year"] == 98000.0
    assert truck_offer["payback_years"] == round(100000 / 98000, 2)
    assert "Transport" in truck_offer["advice"]


def test_trucks_advises_personnel_is_the_limiting_factor(monkeypatch):
    runner, player_id, offer = _truck_runner(personnel_cap=20)
    state = SimpleNamespace(recent_demand={player_id: [100, 100]})
    monkeypatch.setattr(
        "market_sim.game.actions.truck_offers",
        lambda runner, pid: [offer],
    )

    result = world_finance.trucks(runner, state, player_id)
    truck_offer = result["offers"][0]

    assert truck_offer["extra_sales_per_day"] == 0.0
    assert "Personal" in truck_offer["advice"]


def test_trucks_advises_courier_does_not_benefit_from_a_truck(monkeypatch):
    runner, player_id, offer = _truck_runner(transport_mode="courier")
    state = SimpleNamespace(recent_demand={player_id: [100, 100]})
    monkeypatch.setattr(
        "market_sim.game.actions.truck_offers",
        lambda runner, pid: [offer],
    )

    result = world_finance.trucks(runner, state, player_id)
    truck_offer = result["offers"][0]

    assert truck_offer["extra_sales_per_day"] == 0.0
    assert "Kurier" in truck_offer["advice"]


def test_trucks_has_no_payback_when_extra_profit_is_not_positive(monkeypatch):
    runner, player_id, offer = _truck_runner(annual_cost=200000.0)
    state = SimpleNamespace(recent_demand={player_id: [100, 100]})
    monkeypatch.setattr(
        "market_sim.game.actions.truck_offers",
        lambda runner, pid: [offer],
    )

    result = world_finance.trucks(runner, state, player_id)
    truck_offer = result["offers"][0]

    assert truck_offer["extra_sales_per_day"] > 0
    assert truck_offer["extra_profit_year"] <= 0
    assert truck_offer["payback_years"] is None
