from src.lib.Event import GameEvent
from src.lib.projections.ship_info import FighterState, ShipInfo


def game_event(content: dict[str, object]) -> GameEvent:
    return GameEvent(content=content, historic=False)


def test_dock_srv_resets_matching_fighter_only() -> None:
    projection = ShipInfo()
    projection.state.Fighters = [
        FighterState(ID=130, Status="Launched", Pilot="Commander"),
        FighterState(ID=131, Status="Launched", Pilot="NPC Crew"),
    ]

    projection.process(game_event({
        "timestamp": "2026-07-12T20:00:41Z",
        "event": "DockSRV",
        "SRVType": "lander01",
        "SRVType_Localised": "Nomad",
        "ID": 130,
    }))

    assert projection.state.Fighters[0] == FighterState(Status="Ready")
    assert projection.state.Fighters[1] == FighterState(
        ID=131, Status="Launched", Pilot="NPC Crew"
    )

    projection.process(game_event({
        "timestamp": "2026-07-12T20:01:52Z",
        "event": "DockSRV",
        "SRVType": "lander01",
        "SRVType_Localised": "Nomad",
        "ID": 999,
    }))

    assert projection.state.Fighters[1] == FighterState(
        ID=131, Status="Launched", Pilot="NPC Crew"
    )
