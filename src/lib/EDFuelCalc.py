from __future__ import annotations
import re
from typing import Any, Dict, Optional, Tuple

RESET_FUEL_ON_LOADOUT = False

#----Fsd Types
FSD_STATS: Dict[tuple[int, str], dict] = {
    (2,"E"): {"mass":2.50, "opt_mass":48.0,  "max_fuel":0.60},
    (2,"D"): {"mass":1.00, "opt_mass":54.0,  "max_fuel":0.60},
    (2,"C"): {"mass":2.50, "opt_mass":60.0,  "max_fuel":0.60},
    (2,"B"): {"mass":4.00, "opt_mass":75.0,  "max_fuel":0.80},
    (2,"A"): {"mass":2.50, "opt_mass":90.0,  "max_fuel":0.90},

    (3,"E"): {"mass":5.00, "opt_mass":80.0,  "max_fuel":1.20},
    (3,"D"): {"mass":2.00, "opt_mass":90.0,  "max_fuel":1.20},
    (3,"C"): {"mass":5.00, "opt_mass":100.0, "max_fuel":1.20},
    (3,"B"): {"mass":8.00, "opt_mass":125.0, "max_fuel":1.50},
    (3,"A"): {"mass":5.00, "opt_mass":150.0, "max_fuel":1.80},

    (4,"E"): {"mass":10.00,"opt_mass":280.0, "max_fuel":2.00},
    (4,"D"): {"mass":4.00, "opt_mass":315.0, "max_fuel":2.00},
    (4,"C"): {"mass":10.00,"opt_mass":350.0, "max_fuel":2.00},
    (4,"B"): {"mass":16.00,"opt_mass":438.0, "max_fuel":2.50},
    (4,"A"): {"mass":10.00,"opt_mass":525.0, "max_fuel":3.00},

    (5,"E"): {"mass":20.00,"opt_mass":560.0, "max_fuel":3.30},
    (5,"D"): {"mass":8.00, "opt_mass":630.0, "max_fuel":3.30},
    (5,"C"): {"mass":20.00,"opt_mass":700.0, "max_fuel":3.30},
    (5,"B"): {"mass":32.00,"opt_mass":875.0, "max_fuel":4.10},
    (5,"A"): {"mass":20.00,"opt_mass":1050.0,"max_fuel":5.00},

    (6,"E"): {"mass":40.00,"opt_mass":960.0, "max_fuel":5.30},
    (6,"D"): {"mass":16.00,"opt_mass":1080.0,"max_fuel":5.30},
    (6,"C"): {"mass":40.00,"opt_mass":1200.0,"max_fuel":5.30},
    (6,"B"): {"mass":64.00,"opt_mass":1500.0,"max_fuel":6.60},
    (6,"A"): {"mass":40.00,"opt_mass":1800.0,"max_fuel":8.00},

    (7,"E"): {"mass":80.00,"opt_mass":1440.0,"max_fuel":8.50},
    (7,"D"): {"mass":32.00,"opt_mass":1620.0,"max_fuel":8.50},
    (7,"C"): {"mass":80.00,"opt_mass":1800.0,"max_fuel":8.50},
    (7,"B"): {"mass":128.00,"opt_mass":2250.0,"max_fuel":10.60},
    (7,"A"): {"mass":80.00,"opt_mass":2700.0,"max_fuel":12.80},
}

FSD_OVERCHARGE_STATS: Dict[tuple[int, str], dict] = {
    (2,"A"): {"mass":3.25,  "opt_mass":170.0,   "max_fuel":1.00},
    (3,"A"): {"mass":6.50,  "opt_mass":283.9,   "max_fuel":1.90},
    (4,"A"): {"mass":13.00, "opt_mass":994.5,   "max_fuel":3.20},
    (5,"A"): {"mass":26.00, "opt_mass":1997.5,  "max_fuel":5.20},
    (6,"A"): {"mass":52.00, "opt_mass":3400.0,  "max_fuel":8.30},
    (7,"A"): {"mass":104.0, "opt_mass":5100.0,  "max_fuel":13.10},
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

def _find_fsd(modules: list | None) -> Tuple[Optional[int], Optional[str], bool, Optional[float]]:
    if not isinstance(modules, list):
        return None, None, False, None
    for m in modules:
        if m.get("Slot") != "FrameShiftDrive":
            continue
        item = m.get("Item", "")
        over = "hyperdrive_overcharge" in item
        ms = re.search(r"size(\d)", item)
        mc = re.search(r"class(\d)", item)
        size = int(ms.group(1)) if ms else None
        rating = RATING_BY_CLASSNUM.get(int(mc.group(1))) if mc else None
        eng = m.get("Engineering", {}) or {}
        opt = None
        for mod in eng.get("Modifiers", []) or []:
            if mod.get("Label") in ("FSDOptimalMass", "fsdoptimalmass"):
                opt = float(mod.get("Value"))
                break
        return size, rating, over, opt
    return None, None, False, None

def _max_fuel_per_jump(size: Optional[int], rating: Optional[str], over: bool) -> Optional[float]:
    if size is None or rating is None:
        return None
    src = FSD_OVERCHARGE_STATS if over else FSD_STATS
    s = src.get((size, rating))
    return float(s["max_fuel"]) if s else None

def _compute() -> None:
    lo = _state["loadout"] or {}
    if _state["fuel_frac"] is None:
        return

    unladen   = float(lo.get("UnladenMass") or 0.0)
    cargo_cap = float(lo.get("CargoCapacity") or 0.0)
    fuel_cap  = float((lo.get("FuelCapacity") or {}).get("Main") or 0.0)
    d_max     = float(lo.get("MaxJumpRange") or 0.0)

    size, rating, over, _opt_from_eng = _find_fsd(lo.get("Modules"))
    max_fuel = _max_fuel_per_jump(size, rating, over)

    if not (unladen > 0 and fuel_cap > 0 and d_max > 0 and max_fuel):
        return

    cargo_cur = float(_state["cargo_cur"] or 0.0)
    fuel_cur  = max(0.0, min(1.0, float(_state["fuel_frac"]))) * fuel_cap

    M_ref = unladen + max_fuel
    M_cur = unladen + cargo_cur + fuel_cur
    M_min = unladen + cargo_cap + fuel_cap

    if min(M_ref, M_cur, M_min) <= 0:
        return

    cur_ly = d_max * (M_ref / M_cur)
    min_ly = d_max * (M_ref / M_min)

    if cur_ly < 0.0: cur_ly = 0.0
    if min_ly < 0.0: min_ly = 0.0
    if cur_ly > d_max: cur_ly = d_max
    if min_ly > d_max: min_ly = d_max

    _state["last_written"] = (round(min_ly, 2), round(cur_ly, 2), round(d_max, 2))

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
        _compute()

def get_current_jump_range() -> Optional[float]:
    if _state.get("last_written") is None:
        return None
    _, cur, _ = _state["last_written"]
    return float(cur)
