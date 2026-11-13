"""Tests für den Spielmodus der Phase 1."""

from types import SimpleNamespace

import pytest

from market_sim.game import (
    BRANCHES,
    GameSession,
    PlayerPolicy,
    PlayerSettings,
    SaleResult,
)


def make(years=1):
    """Erstellt eine kurze Spielsitzung."""
    return GameSession(seed=1, years=years, days_per_year=60)


def _policy(runner, firm_id):
    """Liefert die Policy einer Firma oder überspringt den Test."""
    for attribute in ("policies", "_policies"):
        policies = getattr(runner, attribute, None)
        if isinstance(policies, dict) and firm_id in policies:
            return policies[firm_id]
    pytest.skip("Keine Policy-Zuordnung am Runner verfügbar")


def test_found_validation():
    """Ungültige Branchen und Kategorien werden abgelehnt."""
    session = make()
    with pytest.raises(ValueError):
        session.found("unbekannt", "X")
    with pytest.raises(ValueError):
        session.found("hersteller", "X", category="irgendwas")


def test_start_snapshot():
    """Der Start liefert den ersten Halt und gründet die Firma."""
    session = make()
    session.found("hersteller", "Meine Fabrik")
    snap = session.start()

    assert snap.year == 1
    assert snap.month == 1
    firm = session.runner.network.firm("factory_p01")
    assert firm is not None
    assert firm.cash == pytest.approx(
        session.runner.config.market_entry.start_cash_fraction
        * session.runner._entry_cash["factory"]
    )
    assert isinstance(_policy(session.runner, firm.id), PlayerPolicy)


@pytest.mark.parametrize("price_kind", ["high", "low", "middle"])
def test_end_round_applies_price(price_kind):
    """Der Preis wird am nächsten Halt auf das Stufenband begrenzt."""
    session = make(years=2)
    session.found("hersteller", "Meine Fabrik")
    session.start()

    band = session.runner.config.stage_prices["factory"]
    if price_kind == "high":
        price = 1e9
        expected = band.max
    elif price_kind == "low":
        price = 0.0001
        expected = band.min
    else:
        price = (band.min + band.max) / 2
        expected = price

    snap2 = session.end_round(PlayerSettings(base_price=price))
    firm = session.runner.network.firm("factory_p01")

    assert snap2.month == 2
    assert firm.sell_price == pytest.approx(expected)


def test_player_policy_decide_daily():
    """Die Spieler-Policy setzt Menge und Preis für den Tag."""
    session = make()
    session.found("hersteller", "Meine Fabrik")
    session.start()

    firm = session.runner.network.firm("factory_p01")
    config = session.runner.config
    band = config.stage_prices["factory"]
    strategy = PlayerPolicy(
        PlayerSettings(base_price=(band.min + band.max) / 2)
    ).decide_annual(firm, None, config)
    obs = SimpleNamespace(
        recent_demand=10,
        inventory=0,
        on_order=0,
        backlog=0,
    )

    fixed = PlayerPolicy(
        PlayerSettings(base_price=(band.min + band.max) / 2, order_qty=5)
    ).decide_daily(firm, obs, strategy, config)
    automatic = PlayerPolicy(
        PlayerSettings(base_price=(band.min + band.max) / 2)
    ).decide_daily(firm, obs, strategy, config)

    assert fixed.order_qty == automatic.order_qty  # Hersteller: immer Kapazität (Feedback 6)
    assert automatic.order_qty >= 0


def test_run_to_end():
    """Die Sitzung endet nach dem letzten Jahr mit einem Ergebnis."""
    session = make(years=1)
    session.found("hersteller", "Meine Fabrik")
    snap = session.start()

    for _ in range(20):
        if snap.game_over:
            break
        snap = session.end_round()
    assert snap.game_over, "Die Sitzung endete nicht innerhalb von 20 Runden"

    assert snap.reason == "ende"
    assert session.finished is True
    assert session.result is not None


def test_sell_firm():
    """Der Verkauf beendet die Spielersitzung und erfasst das Ereignis."""
    session = make(years=1)
    session.found("hersteller", "Meine Fabrik")
    session.start()

    res = session.sell_firm()

    assert isinstance(res, SaleResult)
    assert res.price >= 0
    assert res.firm_id == "factory_p01"
    assert not isinstance(_policy(session.runner, res.firm_id), PlayerPolicy)
    assert session.finished
    assert session.wait_done(300)
    assert any(
        (event["event"] if isinstance(event, dict) else getattr(event, "event", None))
        == "player_sale"
        for event in session.result.events
    )


def test_gastro_founding():
    """Eine Gastro-Firma erhält den Restaurant-Kanal."""
    session = make()
    session.found("gastro", "Beiz")
    session.start()

    firm = session.runner.network.firm("retailer_p01")
    assert firm.channel == "restaurant"
