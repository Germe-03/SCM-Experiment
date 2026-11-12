"""Spielmodus: Bestellung anteilig auf mehrere Lieferanten verteilen (supplier_shares)."""

from market_sim.game.controller import GameController


def _record_splits(env, firm_id):
    seen = []
    original = env._split_order

    def wrapper(firm, candidates, quantity):
        result = original(firm, candidates, quantity)
        if firm.id == firm_id:
            seen.append((quantity, dict(result)))
        return result

    env._split_order = wrapper
    return seen


def test_supplier_shares_split_order_between_suppliers(tmp_path):
    game = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    game.new_game("detailhaendler", "Testhandel")
    ids = [c["id"] for c in game.view("suppliers")["candidates"]]
    assert len(ids) >= 2
    a, b = ids[0], ids[1]
    env = game.session.runner.env
    seen = _record_splits(env, game.snapshot.firm_id)
    game.end_round({}, {"supplier_shares": {a: 3, b: 1}})
    assert seen
    totals = {}
    for quantity, allocation in (item for item in seen if item[0] > 0):
        assert set(allocation) <= {a, b}
        assert sum(allocation.values()) == quantity
        for sid, units in allocation.items():
            totals[sid] = totals.get(sid, 0) + units
    assert totals.get(a, 0) > 0 and totals.get(b, 0) > 0
    assert totals[a] > totals[b]


def test_unknown_supplier_shares_fall_back(tmp_path):
    game = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    game.new_game("detailhaendler", "Testhandel")
    env = game.session.runner.env
    seen = _record_splits(env, game.snapshot.firm_id)
    game.end_round({}, {"supplier_shares": {"gibt_es_nicht": 1}})
    assert seen
    for quantity, allocation in seen:
        assert sum(allocation.values()) <= quantity
