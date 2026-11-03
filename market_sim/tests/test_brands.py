"""Phase 2: brands travel through the chain and stock stays consistent."""

from market_sim.brands import largest_remainder, take_from_stock
from market_sim.run import build_runner


def test_take_from_stock_is_proportional_and_conserving():
    stock = {"a": 30, "b": 10}
    taken = take_from_stock(stock, 20)
    assert taken == {"a": 15, "b": 5}
    assert stock == {"a": 15, "b": 5}
    assert sum(largest_remainder(7, {"x": 1, "y": 1, "z": 1}).values()) == 7


def test_stock_matches_inventory_and_flows_after_a_short_run():
    runner, _ = build_runner(1, 0, days_per_year=40)
    runner.continue_run(runner.start(), 1)
    env = runner.env
    for firm_id, runtime in env.runtimes.items():
        assert sum(runtime.stock.values()) == runtime.inventory, firm_id
        assert len(runtime.incoming_brands) == len(runtime.incoming_shipments)
        assert [sum(p.values()) for p in runtime.incoming_brands] == runtime.incoming_shipments
    sold = sum(env.brand_book.brand_units.values()) if env.brand_book.brand_units else 0
    assert sold >= 0


def test_new_brewery_gets_its_own_brand():
    runner, _ = build_runner(1, 0, days_per_year=10)
    state = runner.start()
    runner.continue_run(state, 1)
    template = runner.network.firm("factory_02").model_copy(
        deep=True, update={"id": "factory_e01", "name": "Neu Bräu", "archetype": "premium", "suppliers": []})
    runner.add_firm(template, state)
    assert runner.env.brand_book.brands_of("factory_e01") == ["factory_e01_brand"]
    assert runner.env.brand_book.brands["factory_e01_brand"].positioning == "premium"


def test_recall_hits_the_brands_of_a_brewery():
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    book = runner.env.brand_book
    before = book.brands["alpen_gold"].reputation
    book.recall("factory_01", 0.15)
    assert book.brands["alpen_gold"].reputation == before - 0.15
