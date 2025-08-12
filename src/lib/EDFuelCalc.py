from __future__ import annotations
import re
from typing import Any, Dict, Optional, Tuple

RESET_FUEL_ON_LOADOUT = False

#----Fsd Types
FSD_STATS: Dict[tuple[int, str], dict] = { #Normal FSD
    (2,"E"): {"mass":2.50, "opt_mass":48.0,  "max_fuel":0.60, "linear_const": 11.0, "power_const": 2.00},
    (2,"D"): {"mass":1.00, "opt_mass":54.0,  "max_fuel":0.60, "linear_const": 10.0, "power_const": 2.00},
    (2,"C"): {"mass":2.50, "opt_mass":60.0,  "max_fuel":0.60, "linear_const": 8.00, "power_const": 2.00},
    (2,"B"): {"mass":4.00, "opt_mass":75.0,  "max_fuel":0.80, "linear_const": 10.00, "power_const": 2.00},
    (2,"A"): {"mass":2.50, "opt_mass":90.0,  "max_fuel":0.90, "linear_const": 12.00, "power_const": 2.00},

    (3,"E"): {"mass":5.00, "opt_mass":80.0,  "max_fuel":1.20, "linear_const": 11.0, "power_const": 2.15},
    (3,"D"): {"mass":2.00, "opt_mass":90.0,  "max_fuel":1.20, "linear_const": 10.0, "power_const": 2.15},
    (3,"C"): {"mass":5.00, "opt_mass":100.0, "max_fuel":1.20, "linear_const": 8.00, "power_const": 2.15},
    (3,"B"): {"mass":8.00, "opt_mass":125.0, "max_fuel":1.50, "linear_const": 10.00, "power_const": 2.15},
    (3,"A"): {"mass":5.00, "opt_mass":150.0, "max_fuel":1.80, "linear_const": 12.00, "power_const": 2.15},

    (4,"E"): {"mass":10.00,"opt_mass":280.0, "max_fuel":2.00, "linear_const": 11.0, "power_const": 2.30},
    (4,"D"): {"mass":4.00, "opt_mass":315.0, "max_fuel":2.00, "linear_const": 10.0, "power_const": 2.30},
    (4,"C"): {"mass":10.00,"opt_mass":350.0, "max_fuel":2.00, "linear_const": 8.00, "power_const": 2.30},
    (4,"B"): {"mass":16.00,"opt_mass":438.0, "max_fuel":2.50, "linear_const": 10.00, "power_const": 2.30},
    (4,"A"): {"mass":10.00,"opt_mass":525.0, "max_fuel":3.00, "linear_const": 12.00, "power_const": 2.30},

    (5,"E"): {"mass":20.00,"opt_mass":560.0, "max_fuel":3.30, "linear_const": 11.0, "power_const": 2.45},
    (5,"D"): {"mass":8.00, "opt_mass":630.0, "max_fuel":3.30, "linear_const": 10.0, "power_const": 2.45},
    (5,"C"): {"mass":20.00,"opt_mass":700.0, "max_fuel":3.30, "linear_const": 8.00, "power_const": 2.45},
    (5,"B"): {"mass":32.00,"opt_mass":875.0, "max_fuel":4.10, "linear_const": 10.00, "power_const": 2.45},
    (5,"A"): {"mass":20.00,"opt_mass":1050.0,"max_fuel":5.00, "linear_const": 12.00, "power_const": 2.45},

    (6,"E"): {"mass":40.00,"opt_mass":960.0, "max_fuel":5.30, "linear_const": 11.0, "power_const": 2.60},
    (6,"D"): {"mass":16.00,"opt_mass":1080.0,"max_fuel":5.30, "linear_const": 10.0, "power_const": 2.60},
    (6,"C"): {"mass":40.00,"opt_mass":1200.0,"max_fuel":5.30, "linear_const": 8.00, "power_const": 2.60},
    (6,"B"): {"mass":64.00,"opt_mass":1500.0,"max_fuel":6.60, "linear_const": 10.00, "power_const": 2.60},
    (6,"A"): {"mass":40.00,"opt_mass":1800.0,"max_fuel":8.00, "linear_const": 12.00, "power_const": 2.60},

    (7,"E"): {"mass":80.00,"opt_mass":1440.0,"max_fuel":8.50, "linear_const": 11.0, "power_const": 2.75},
    (7,"D"): {"mass":32.00,"opt_mass":1620.0,"max_fuel":8.50, "linear_const": 10.0, "power_const": 2.75},
    (7,"C"): {"mass":80.00,"opt_mass":1800.0,"max_fuel":8.50, "linear_const": 8.00, "power_const": 2.75},
    (7,"B"): {"mass":128.00,"opt_mass":2250.0,"max_fuel":10.60, "linear_const": 10.00, "power_const": 2.75},
    (7,"A"): {"mass":80.00,"opt_mass":2700.0,"max_fuel":12.80, "linear_const": 12.00, "power_const": 2.75},

    # 8 ?
}
FSD_OVERCHARGE_STATS: Dict[tuple[int, str], dict] = {# FSD SCO
    (2,"E"): {"mass": 2.50, "opt_mass": 60.0,  "max_fuel": 0.60, "linear_const": 8.0,  "power_const": 2.00},
    (2,"D"): {"mass": 2.50, "opt_mass": 90.0,  "max_fuel": 0.90, "linear_const": 12.0, "power_const": 2.00},
    (2,"C"): {"mass": 2.50, "opt_mass": 90.0,  "max_fuel": 0.90, "linear_const": 12.0, "power_const": 2.00},
    (2,"B"): {"mass": 2.50, "opt_mass": 90.0,  "max_fuel": 0.90, "linear_const": 12.0, "power_const": 2.00},
    (2,"A"): {"mass": 2.50, "opt_mass": 100.0, "max_fuel": 1.00, "linear_const": 13.0, "power_const": 2.00},

    (3,"E"): {"mass": 5.00, "opt_mass": 100.0, "max_fuel": 1.20, "linear_const": 8.0,  "power_const": 2.15},
    (3,"D"): {"mass": 2.00, "opt_mass": 150.0, "max_fuel": 1.80, "linear_const": 12.0, "power_const": 2.15},
    (3,"C"): {"mass": 5.00, "opt_mass": 150.0, "max_fuel": 1.80, "linear_const": 12.0, "power_const": 2.15},
    (3,"B"): {"mass": 5.00, "opt_mass": 150.0, "max_fuel": 1.80, "linear_const": 12.0, "power_const": 2.15},
    (3,"A"): {"mass": 5.00, "opt_mass": 167.0, "max_fuel": 1.90, "linear_const": 13.0, "power_const": 2.15},

    (4,"E"): {"mass": 10.00, "opt_mass": 350.0, "max_fuel": 2.00, "linear_const": 8.0,  "power_const": 2.30},
    (4,"D"): {"mass": 4.00,  "opt_mass": 525.0, "max_fuel": 3.00, "linear_const": 12.0, "power_const": 2.30},
    (4,"C"): {"mass": 10.00, "opt_mass": 525.0, "max_fuel": 3.00, "linear_const": 12.0, "power_const": 2.30},
    (4,"B"): {"mass": 10.00, "opt_mass": 525.0, "max_fuel": 3.00, "linear_const": 12.0, "power_const": 2.30},
    (4,"A"): {"mass": 10.00, "opt_mass": 585.0, "max_fuel": 3.20, "linear_const": 13.0, "power_const": 2.30},

    (5,"E"): {"mass": 20.00, "opt_mass": 700.0, "max_fuel": 3.30, "linear_const": 8.0,  "power_const": 2.45},
    (5,"D"): {"mass": 8.00,  "opt_mass": 1050.0,"max_fuel": 5.00, "linear_const": 12.0, "power_const": 2.45},
    (5,"C"): {"mass": 20.00, "opt_mass": 1050.0,"max_fuel": 5.00, "linear_const": 12.0, "power_const": 2.45},
    (5,"B"): {"mass": 20.00, "opt_mass": 1050.0,"max_fuel": 5.00, "linear_const": 12.0, "power_const": 2.45},
    (5,"A"): {"mass": 20.00, "opt_mass": 1175.0,"max_fuel": 5.20, "linear_const": 13.0, "power_const": 2.45},

    (6,"E"): {"mass": 40.00, "opt_mass": 1200.0,"max_fuel": 5.30, "linear_const": 8.0,  "power_const": 2.60},
    (6,"D"): {"mass": 16.00, "opt_mass": 1800.0,"max_fuel": 8.00, "linear_const": 12.0, "power_const": 2.60},
    (6,"C"): {"mass": 40.00, "opt_mass": 1800.0,"max_fuel": 8.00, "linear_const": 12.0, "power_const": 2.60},
    (6,"B"): {"mass": 40.00, "opt_mass": 1800.0,"max_fuel": 8.00, "linear_const": 12.0, "power_const": 2.60},
    (6,"A"): {"mass": 40.00, "opt_mass": 2000.0,"max_fuel": 8.30, "linear_const": 13.0, "power_const": 2.60},

    (7,"E"): {"mass": 80.00, "opt_mass": 1800.0,"max_fuel": 8.50, "linear_const": 8.0,  "power_const": 2.75},
    (7,"D"): {"mass": 32.00, "opt_mass": 2700.0,"max_fuel": 12.80,"linear_const": 12.0, "power_const": 2.75},
    (7,"C"): {"mass": 80.00, "opt_mass": 2700.0,"max_fuel": 12.80,"linear_const": 12.0, "power_const": 2.75},
    (7,"B"): {"mass": 80.00, "opt_mass": 2700.0,"max_fuel": 12.80,"linear_const": 12.0, "power_const": 2.75},
    (7,"A"): {"mass": 80.00, "opt_mass": 3000.0,"max_fuel": 13.10,"linear_const": 13.0, "power_const": 2.75},
}






FSD_OVERCHARGE_V1PRE_STATS: Dict[tuple[int, str], dict] = {# FSD V1Pre
    (2,"A"): {"mass":3.25,  "opt_mass":170.0,   "max_fuel":1.00, "linear_const": 12.00, "power_const": 2.00},
    (3,"A"): {"mass":6.50,  "opt_mass":283.9,   "max_fuel":1.90, "linear_const": 12.00, "power_const": 2.15},
    (4,"A"): {"mass":13.00, "opt_mass":994.5,   "max_fuel":3.20, "linear_const": 12.00, "power_const": 2.30},
    (5,"A"): {"mass":26.00, "opt_mass":1997.5,  "max_fuel":5.20, "linear_const": 12.00, "power_const": 2.45},
    (6,"A"): {"mass":52.00, "opt_mass":3400.0,  "max_fuel":8.30, "linear_const": 12.00, "power_const": 2.60},
    (7,"A"): {"mass":104.0, "opt_mass":5100.0,  "max_fuel":13.10, "linear_const": 12.00, "power_const": 2.75},
}
FSD_GUARDIAN_BOOSTER: Dict[tuple[int, str], dict] = {
    (1,"H"): {"jump_boost": 4.00},
    (2,"H"): {"jump_boost": 6.00},
    (3,"H"): {"jump_boost": 7.75},
    (4,"H"): {"jump_boost": 9.25},
    (5,"H"): {"jump_boost": 10.50},
}

RATING_BY_CLASSNUM = {1:"E", 2:"D", 3:"C", 4:"B", 5:"A"}

#----hard reset
_state: Dict[str, Any] = {
    "loadout": None,
    "cargo_cur": 0.0,
    "fuel_frac": None,
    "last_written": None,
    "last_trigger_id": None
}

#--ask for event
def ingest_event(event: Any) -> None:
    try:
        kind = getattr(event, "kind", None)
        trigger_id = getattr(event, "id", None)
        trigger_write = False

        if kind == "game":
            evt = getattr(event, "content", {}) or {}
            et  = evt.get("event", "")

            if et == "Loadout":
                _state["loadout"] = evt
                _state["cargo_cur"] = 0.0
                if RESET_FUEL_ON_LOADOUT:
                    _state["fuel_frac"] = None
                _state["last_written"] = None
                _state["last_trigger_id"] = None

            elif et == "Cargo" and evt.get("Vessel") == "Ship":
                if "Count" in evt:
                    _state["cargo_cur"] = float(evt.get("Count", 0.0))
                trigger_write = True

            elif et == "FSDJump":
                lo = _state["loadout"] or {}
                fuel_cap = float((lo.get("FuelCapacity") or {}).get("Main") or 0.0)
                fuel_level_t = evt.get("FuelLevel")
                if fuel_cap > 0 and isinstance(fuel_level_t, (int, float)):
                    _state["fuel_frac"] = max(0.0, min(1.0, float(fuel_level_t) / fuel_cap))
                trigger_write = True

        elif kind == "status":
            st = getattr(event, "status", {}) or {}
            if st.get("event") == "Status":
                fuel = st.get("Fuel")
                if isinstance(fuel, dict) and "FuelMain" in fuel:
                    lo = _state["loadout"] or {}
                    fuel_cap = float((lo.get("FuelCapacity") or {}).get("Main") or 0.0)
                    if fuel_cap > 0:
                        fuel_main_t = float(fuel["FuelMain"])
                        _state["fuel_frac"] = max(0.0, min(1.0, fuel_main_t / fuel_cap))
                        trigger_write = True

    except Exception:
        return

    if trigger_write:
        if _state["last_trigger_id"] is not None and _state["last_trigger_id"] == trigger_id:
            return
        _state["last_trigger_id"] = trigger_id
       

def get_current_jump_range() -> Optional[float]:
    if _state.get("last_written") is None:
        return None
    _, cur, _ = _state["last_written"]
    return float(cur)
