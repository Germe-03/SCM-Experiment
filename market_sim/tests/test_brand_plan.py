from market_sim.game.controller import GameController


def _brand_share(env, firm_id, brand_id):
    stock = env.runtimes[firm_id].stock
    total = sum(stock.values())
    return stock.get(brand_id, 0) / total if total else 0.0


def test_brand_catalog_and_demand_by_category(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("detailhaendler", "T")
    runner = controller.session.runner
    book = runner.env.brand_book
    catalog = book.brand_catalog(runner, controller.snapshot.firm_id)
    assert catalog
    for key in ("id", "name", "category", "owner", "owner_name", "positioning", "value",
                "quality", "reputation", "price", "demand_share"):
        assert key in catalog[0]
    demand = book.demand_by_category(runner)
    assert demand and all(v >= 0 for v in demand.values()) and sum(demand.values()) > 0
    assert isinstance(book.demand_by_category(runner, region="nowhere"), dict)


def test_brand_plan_raises_brand_share_in_stock(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("detailhaendler", "T")
    runner = controller.session.runner
    env = runner.env
    firm_id = controller.snapshot.firm_id
    catalog = runner.env.brand_book.brand_catalog(runner, firm_id)
    brand_id = catalog[0]["id"]
    before = _brand_share(env, firm_id, brand_id)
    for _ in range(3):
        state = controller.end_round({}, {"brand_plan": {brand_id: 300000}})
        assert "error" not in state
    assert _brand_share(env, firm_id, brand_id) > before
