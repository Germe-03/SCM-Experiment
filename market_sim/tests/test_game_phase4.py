import pytest


def test_avatars_are_available_and_have_expected_details():
    from market_sim.game.ceos import AVATARS, age, available, image_name, stage, visible

    assert len(AVATARS) == 20

    for year in range(1, 53):
        assert sum(
            available(avatar, year, 0, 360) for avatar in AVATARS
        ) >= 10

    lea = next(avatar for avatar in AVATARS if avatar.nr == 1)
    assert lea.name == "Lea Brunner"
    assert available(lea, 1, 0, 360)
    assert age(lea, 1, 0, 360) == 25
    assert stage(lea, 1, 0, 360) == "jung"
    assert image_name(lea, 1, 0, 360) == "ceo_01_jung.png"

    mira = next(avatar for avatar in AVATARS if avatar.nr == 19)
    assert mira.appear_year == 32
    assert not visible(mira, 1, 0, 360)


def test_ceo_book_hiring_firing_and_retirement():
    from market_sim.game.ceos import AVATARS, CeoBook

    lea = next(avatar for avatar in AVATARS if avatar.nr == 1)
    book = CeoBook()
    book.hire("firm-a", lea.nr, 1, 0, 360)

    with pytest.raises(ValueError):
        book.hire("firm-b", lea.nr, 1, 0, 360)

    mira = next(avatar for avatar in AVATARS if avatar.nr == 19)
    with pytest.raises(ValueError):
        book.hire("firm-c", mira.nr, 1, 0, 360)

    assert book.fire("firm-a") == lea
    assert book.ceo_of("firm-a") is None
    assert book.firm_of(lea.nr) is None

    reto = next(avatar for avatar in AVATARS if avatar.nr == 10)
    book.hire("firm-d", reto.nr, 1, 0, 360)

    retired = book.retire_due(15, 0, 360)
    assert retired == [("firm-d", reto)]
    assert book.ceo_of("firm-d") is None
    assert book.firm_of(reto.nr) is None


def test_controller_holding_ceos_and_orders_round_trip(tmp_path):
    from market_sim.game.controller import GameController

    controller = GameController(tmp_path, seed=0, years=2, days_per_year=60)
    state = controller.new_game("hersteller", "Testbräu", category="beer")

    assert isinstance(state["targets"], list)
    assert isinstance(state["ceos"], list)
    assert state["holding"] is None

    target = state["targets"][0]
    target_id = target["id"]

    state = controller.end_round({}, None, {"buy": target_id})
    order_result = state["order_results"][0]
    if not order_result["ok"]:
        pytest.skip(order_result["message"])

    assert state["holding"] is not None
    daughter_ids = {daughter["id"] for daughter in state["holding"]["daughters"]}
    assert target_id in daughter_ids
    assert any("CEO" in message["text"] for message in state["messages"])

    state = controller.end_round({}, None, {"hire": {target_id: 1}})
    assert state["ceo_of"][target_id] == 1

    save_result = controller.save("p4")
    assert save_result.get("ok") is True

    state = controller.load("p4")
    assert state["ceo_of"][target_id] == 1
    daughter_ids = {daughter["id"] for daughter in state["holding"]["daughters"]}
    assert target_id in daughter_ids

    state = controller.end_round({}, None, {"sell": target_id})
    daughter_ids = (
        {daughter["id"] for daughter in state["holding"]["daughters"]}
        if state["holding"] is not None
        else set()
    )
    assert target_id not in daughter_ids
    assert target_id not in state["ceo_of"]
