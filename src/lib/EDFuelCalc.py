from __future__ import annotations

#----Fsd Types
FSD_STATS: dict[tuple[int, str], dict] = { #Normal FSD
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

    (8,"D"): {"mass":1,"opt_mass":1,"max_fuel":1, "linear_const": 1, "power_const": 1},
    (8,"C"): {"mass":1,"opt_mass":1,"max_fuel":1, "linear_const": 1, "power_const": 1},
    # 8 ?
}
FSD_OVERCHARGE_STATS: dict[tuple[int, str], dict] = {# FSD SCO
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

FSD_OVERCHARGE_V2PRE_STATS: dict[tuple[int, str], dict] = {# FSD V1Pre
    (2,"A"): {"mass":3.25,   "max_fuel":1.00, "linear_const": 12.00, "power_const": 2.00},
    (3,"A"): {"mass":6.50,   "max_fuel":1.90, "linear_const": 12.00, "power_const": 2.15},
    (4,"A"): {"mass":13.00,   "max_fuel":3.20, "linear_const": 12.00, "power_const": 2.30},
    (5,"A"): {"mass":26.00,  "max_fuel":5.20, "linear_const": 12.00, "power_const": 2.45},
    (6,"A"): {"mass":52.00,  "max_fuel":8.30, "linear_const": 12.00, "power_const": 2.60},
    (7,"A"): {"mass":104.00,  "max_fuel":13.10, "linear_const": 12.00, "power_const": 2.75},
}


FSD_GUARDIAN_BOOSTER: dict[tuple[int, str], dict] = {
    (1,"H"): {"jump_boost": 4.00},
    (2,"H"): {"jump_boost": 6.00},
    (3,"H"): {"jump_boost": 7.75},
    (4,"H"): {"jump_boost": 9.25},
    (5,"H"): {"jump_boost": 10.50},
}

RATING_BY_CLASSNUM = {1:"E", 2:"D", 3:"C", 4:"B", 5:"A"}
