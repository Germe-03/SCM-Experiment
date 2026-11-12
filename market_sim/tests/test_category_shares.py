from market_sim.game.controller import GameController


def _wine_share(env, firm_id):
    stock = env.stock_by_category(firm_id)
    total = sum(stock.values())
    return stock.get("wine", 0) / total if total else 0.0


def test_player_category_shares_shift_stock_to_wine(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("detailhaendler", "T")
    runner = controller.session.runner
    env = runner.env
    firm_id = controller.snapshot.firm_id
    assert isinstance(env.stock_by_category(firm_id), dict)
    before = _wine_share(env, firm_id)
    for _ in range(3):
        state = controller.end_round({}, {"category_shares": {"wine": 1}})
        assert "error" not in state
    after = _wine_share(env, firm_id)
    assert after > before + 0.1
