from types import SimpleNamespace

from market_sim.stock_market import StockMarket, EtfBook


def _market() -> StockMarket:
    return StockMarket.__new__(StockMarket)


def _runner(holding_groups=None, mergers=None) -> SimpleNamespace:
    return SimpleNamespace(
        holding_groups=holding_groups,
        mergers=mergers,
        network=SimpleNamespace(firm=lambda i: SimpleNamespace(name=i.upper())),
    )


def _state(events=None) -> SimpleNamespace:
    return SimpleNamespace(events=list(events or []))


def test_delisting_reason_for_holding():
    group = SimpleNamespace(
        id="grp1",
        name="X Holding",
        listing_id="root",
        dissolved_year=None,
    )
    holding_groups = SimpleNamespace(
        group_of=lambda fid: group if fid == "sub" else None,
        groups={"grp1": group},
        sub_of={"sub": "grp1"},
    )
    assert _market().delisting_reason(_runner(holding_groups=holding_groups), _state(), "sub") == (
        "holding",
        "grp1",
    )


def test_delisting_reason_for_merger():
    mergers = SimpleNamespace(log=[{"parents": ["a", "b"], "new": "c"}])
    assert _market().delisting_reason(_runner(mergers=mergers), _state(), "a") == (
        "merger",
        "c",
    )


def test_delisting_reason_for_takeover():
    event = {
        "firm": "t",
        "event": "takeover",
        "details": "gekauft von buyer_1 für CHF 5",
    }
    assert _market().delisting_reason(_runner(), _state([event]), "t") == (
        "takeover",
        "buyer_1",
    )


def test_delisting_reason_for_bankruptcy():
    event = {"firm": "f", "event": "bankruptcy"}
    assert _market().delisting_reason(_runner(), _state([event]), "f") == (
        "bankruptcy",
        None,
    )


def test_delisting_reason_defaults_to_exit():
    assert _market().delisting_reason(_runner(), _state(), "f") == ("exit", None)


def test_etf_groups_for_factory_include_category():
    firm = SimpleNamespace(
        region="CH",
        stage="factory",
        channel="",
        category="softdrinks",
    )
    assert ("category", "softdrinks") in EtfBook.groups_for(firm)
