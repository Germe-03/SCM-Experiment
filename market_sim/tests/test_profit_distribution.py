from types import SimpleNamespace

from market_sim.profit_distribution import ProfitDistribution


class RT(SimpleNamespace):
    def adjust_cash(self, delta, reason="sonstiges"):
        self.cash += delta
        self.flows[reason] = self.flows.get(reason, 0.0) + delta


def rt(cash=10000.0):
    return RT(cash=cash, flows={})


def test_loss_carryforward_blocks_dividend_and_is_offset():
    d, r = ProfitDistribution(), rt()
    row = d.distribute(1, "f", r, -100.0, 1000.0, 10.0)
    assert row["dividend"] == 0 and d.accounts["f"]["loss_carryforward"] == 100.0
    row = d.distribute(2, "f", r, 60.0, 1000.0, 10.0)
    assert row["loss_offset"] == 60.0 and row["dividend"] == 0
    row = d.distribute(3, "f", r, 140.0, 1000.0, 10.0)
    assert row["loss_offset"] == 40.0 and d.accounts["f"]["loss_carryforward"] == 0
    assert abs(row["legal_reserve_add"] - 5.0) < 1e-9


def test_reserve_capped_at_half_capital():
    d, r = ProfitDistribution(), rt()
    for y in range(5):
        d.distribute(y, "f", r, 1000.0, 100.0, 1.0)
    assert d.accounts["f"]["legal_reserve"] == 50.0


def test_withholding_tax_35_percent():
    d, r = ProfitDistribution(), rt()
    row = d.distribute(1, "f", r, 1000.0, 100000.0, 1.0)
    assert abs(row["dividend"] - 0.4 * 950.0) < 1e-9
    assert abs(r.flows["staat:Verrechnungssteuer"] + 0.35 * row["dividend"]) < 1e-9
    assert abs(r.flows["dividende:aktionaere"] + 0.65 * row["dividend"]) < 1e-9
    assert abs(d.accounts["f"]["retained"] - 570.0) < 1e-9


def test_no_dividend_when_cash_too_low():
    d, r = ProfitDistribution(), rt(cash=100.0)
    row = d.distribute(1, "f", r, 1000.0, 1000.0, 50.0)
    assert row["dividend"] == 0 and r.flows == {}
    assert d.export()["rows"] == d.history


def test_subsidiary_pays_parent():
    d, r, p = ProfitDistribution(), rt(), rt(0.0)
    row = d.distribute(1, "s", r, 1000.0, 100000.0, 1.0, parent_runtime=p)
    assert p.cash == row["dividend"] > 0 and "staat:Verrechnungssteuer" not in r.flows
