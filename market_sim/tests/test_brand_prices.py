import json

from market_sim.game.controller import GameController


def _new(tmp_path):
    game = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    game.new_game("detailhaendler", "Testfirma")
    return game


def test_brand_prices_in_purchasing_and_retail_price(tmp_path):
    game = _new(tmp_path)
    view = game.view("purchasing")
    assert view["brands"]
    json.dumps(view)
    item = view["brands"][0]
    assert "sell_price" in item and "rival_price" in item

    runner = game.session.runner
    pid = game.session._firm_id
    book = runner.env.brand_book
    brand = book.brands[item["id"]]
    firm = runner.network.firm(pid)
    book.player_choices = runner.player_choices
    base = book.retail_price(firm.sell_price, brand, firm)
    runner.player_choices[pid].brand_prices = {brand.id: base * 2}
    assert abs(book.retail_price(firm.sell_price, brand, firm) - base * 2) < 1e-9
    other = [f for f in runner.network.firms_in("retailer") if f.id != pid][0]
    assert book.retail_price(other.sell_price, brand, other) == book.retail_price(other.sell_price, brand, other)
    assert game.view("purchasing")["brands"][0]["sell_price"] == round(base * 2, 4)


def test_trucks_fields_json(tmp_path):
    game = _new(tmp_path)
    view = game.view("trucks")
    json.dumps(view)
    for offer in view["offers"]:
        assert {"courier_cost_year", "own_cost_year", "saving_year"} <= offer.keys()
