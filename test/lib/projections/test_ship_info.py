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


def test_fighter_loadout_tracks_launch_and_is_cleared_on_reset() -> None:
    projection = ShipInfo()
    projection.state.Fighters = [FighterState(Status="Ready")]

    projection.process(game_event({
        "timestamp": "2026-07-31T23:30:31Z",
        "event": "LaunchFighter",
        "Loadout": "base",
        "ID": 130,
        "PlayerControlled": True,
    }))

    assert projection.state.Fighters[0] == FighterState(
        ID=130, Status="Launched", Pilot="Commander"
    )
    assert projection.state.fighter_loadout == "base"

    projection.process(game_event({
        "timestamp": "2026-07-31T23:31:31Z",
        "event": "DockFighter",
        "ID": 130,
    }))

    assert projection.state.Fighters[0] == FighterState(Status="Ready")
    assert projection.state.fighter_loadout is None


def test_died_and_srv_destroyed_clear_fighter_loadouts() -> None:
    projection = ShipInfo()

    for event_name in ("Died", "SRVDestroyed"):
        projection.state.Fighters = [FighterState(ID=130, Status="Launched", Pilot="Commander")]
        projection.state.fighter_loadout = "base"

        projection.process(game_event({
            "timestamp": "2026-07-31T23:30:31Z",
            "event": event_name,
        }))

        assert projection.state.fighter_loadout is None
