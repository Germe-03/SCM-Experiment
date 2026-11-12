import statistics

from market_sim.game.controller import GameController


def test_initial_listings_have_no_systematic_crash(tmp_path):
    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    controller.new_game("detailhaendler", "T")
    market = controller.session.runner.stock_market
    controller.end_round({})
    rows = market.daily_rows
    assert len(rows) >= 30
    first, later = rows[0], rows[29]
    meta = {"global_day", "year", "day", "index"}
    changes = [later[k] / first[k] - 1 for k in first if k not in meta and k in later]
    assert changes
    assert -0.15 <= statistics.median(changes) <= 0.15
