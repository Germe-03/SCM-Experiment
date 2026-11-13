import pytest

from market_sim.game.controller import GameController


def make(path):
    controller = GameController(path, seed=0, years=2, days_per_year=60)
    state = controller.new_game("grosshaendler", "T")
    assert "error" not in state, state
    return controller


def parts(controller):
    session = controller.session
    runner = session.runner
    return runner, session._firm_id


def pick_retailer(runner):
    return sorted(runner.network.firms_in("retailer"), key=lambda f: f.id)[0]


def run_rounds(controller, rounds=2):
    for _ in range(rounds):
        state = controller.end_round({})
        assert "error" not in state, state


def test_contract_pairs_allowed_and_refused(tmp_path):
    runner, player = parts(make(tmp_path))
    book = runner.contracts
    retailer = pick_retailer(runner)
    distributor = sorted(runner.network.firms_in("distributor"), key=lambda f: f.id)[0]
    factory = sorted(runner.network.firms_in("factory"), key=lambda f: f.id)[0]
    assert book.pair_error(player, retailer.id) is None
    assert book.pair_error(distributor.id, player) is None
    for supplier, buyer in [(retailer.id, player), (factory.id, retailer.id), (player, factory.id),
                            (player, player)]:
        with pytest.raises(ValueError):
            book.propose(supplier, buyer, 1, 1.0, 10)
    assert book.contracts == []


def test_contract_accepted_by_ai_and_delivered_at_contract_price(tmp_path):
    controller = make(tmp_path)
    runner, player = parts(controller)
    retailer = pick_retailer(runner)
    market = runner.network.firm(player).sell_price
    price = market * 1.04  # innerhalb der 5 % Toleranz des Kunden
    contract = runner.contracts.propose(player, retailer.id, 1, price, 100, proposed_by=player)
    assert contract["status"] == "angeboten"
    revenue_before = runner.env.runtimes[player].revenue
    run_rounds(controller, 1)
    assert contract["status"] == "aktiv"
    assert contract in runner.contracts.active_for(player)
    assert contract["ordered"] > 0
    assert 0 < contract["delivered"] <= contract["ordered"]
    assert runner.env.delivery_book[retailer.id][player]["delivered"] >= contract["delivered"]
    assert runner.env.runtimes[player].revenue > revenue_before
    view = runner.contracts.view(contract)
    assert view["units_per_day"] == runner.config.unit_scale.real_units_per_sim_unit


def test_ai_declines_bad_price_or_too_large_quantity(tmp_path):
    controller = make(tmp_path)
    runner, player = parts(controller)
    retailer = pick_retailer(runner)
    market = runner.network.firm(player).sell_price
    expensive = runner.contracts.propose(player, retailer.id, 1, market * 2, 100, proposed_by=player)
    run_rounds(controller, 1)
    assert expensive["status"] == "abgelehnt"
    huge = runner.contracts.propose(player, retailer.id, 10 ** 9, market, 100, proposed_by=player)
    run_rounds(controller, 1)
    assert huge["status"] == "abgelehnt"


def test_cancel_and_decline(tmp_path):
    runner, player = parts(make(tmp_path))
    book = runner.contracts
    retailer = sorted(runner.network.firms_in('distributor'), key=lambda f: f.id)[0]
    first = book.propose(retailer.id, player, 1, 1.0, 10, proposed_by=retailer.id)
    assert first in book.offers_for(player)
    book.accept(first["id"])
    assert first["status"] == "aktiv"
    book.cancel(first["id"])
    assert first["status"] == "beendet"
    second = book.propose(retailer.id, player, 1, 1.0, 10, proposed_by=retailer.id)
    book.decline(second["id"])
    assert second["status"] == "abgelehnt"


def snapshot(controller):
    runner, _ = parts(controller)
    return [(fid, rt.cash, rt.inventory, rt.revenue) for fid, rt in sorted(runner.env.runtimes.items())]


def test_without_contract_identical_runs(tmp_path):
    first, second = make(tmp_path / "a"), make(tmp_path / "b")
    run_rounds(first)
    run_rounds(second)
    assert snapshot(first) == snapshot(second)


def test_contract_ends_when_a_side_goes_bankrupt(tmp_path):
    from market_sim.game.controller import GameController
    c = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    c.new_game("grosshaendler", "T")
    runner = c.session.runner
    book = runner.contracts
    me = c.snapshot.firm_id
    buyer = next(p["id"] for p in book.partners(me) if p["role"] == "Kunde")
    contract = book.propose(me, buyer, 1, 5.0, 300, proposed_by=me)
    book.accept(contract["id"])
    runner.env.runtimes[buyer].active = False
    book._refresh()
    assert contract["status"] == "beendet"
    assert "Konkurs" in contract["end_reason"]


def test_player_change_decided_by_ai_and_ai_change_accepted(tmp_path):
    controller = make(tmp_path)
    runner, player = parts(controller)
    book = runner.contracts
    retailer = pick_retailer(runner)
    market = runner.network.firm(player).sell_price
    contract = book.propose(player, retailer.id, 1, market * 1.04, 200, proposed_by=player)
    run_rounds(controller, 1)
    assert contract["status"] == "aktiv"
    contract["change"] = None  # evtl. KI-Vorschlag des Quartals verwerfen
    # Spieler schlägt zu hohen Preis vor: KI lehnt ab, alter Vertrag gilt
    book.propose_change_bottles(contract["id"], player, None, market * 3)
    assert contract["change"]["proposed_by"] == player
    old_price = contract["price"]
    run_rounds(controller, 1)
    assert contract["price"] == old_price
    assert contract["change_result"]["status"] == "abgelehnt"
    contract["change"] = None
    # Vernünftiger Vorschlag wird angenommen
    book.propose_change(contract["id"], player, 2, market * 1.02)
    run_rounds(controller, 1)
    assert contract["change_result"]["status"] == "angenommen" and contract["units_per_day"] == 2
    assert contract["price"] == pytest.approx(market * 1.02)
    # KI-Vorschlag: Spieler nimmt an
    book.propose_change(contract["id"], retailer.id, 3, 1.5)
    with pytest.raises(ValueError):
        book.propose_change(contract["id"], "unbekannt", 1, 1.0)
    book.accept_change(contract["id"])
    assert contract["units_per_day"] == 3 and contract["price"] == 1.5 and contract["change"] is None
    book.propose_change(contract["id"], retailer.id, 4, 2.0)
    book.decline_change(contract["id"])
    assert contract["units_per_day"] == 3
    with pytest.raises(ValueError):
        book.accept_change(contract["id"])
