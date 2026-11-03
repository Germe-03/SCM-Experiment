"""Phase 2: consumer classes buy brands below their maximum price."""

from market_sim.run import build_runner


def _env():
    runner, _ = build_runner(1, 0, days_per_year=10)
    runner.start()
    return runner.env


def test_nobody_buys_when_every_price_exceeds_the_maximum():
    env = _env()
    for firm in env.network.firms_in("retailer"):
        firm.sell_price = 11.5
    requested, sold, lost = env.brand_book.fulfill(env, 200)
    assert sum(sold.values()) == 0 and lost == 200


def test_higher_brand_reputation_raises_willingness_to_pay():
    env = _env()
    book = env.brand_book
    cls = book.classes["income_2_35-64_regular"]
    slope = env.config.consumers.wtp_slope
    assert cls.max_price * (1 + slope * (0.9 - 0.5)) > cls.max_price * (1 + slope * (0.5 - 0.5))


def test_price_increase_drives_out_low_income_classes_first():
    env = _env()
    for firm in env.network.firms_in("retailer"):
        firm.sell_price *= 1.35
    book = env.brand_book
    book.fulfill(env, 250)
    stats = book.class_stats
    poor = stats["income_1_35-64_regular"]
    rich = stats["income_5_35-64_regular"]
    assert poor.bought / poor.demand < rich.bought / rich.demand
