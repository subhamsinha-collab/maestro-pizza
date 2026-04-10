"""
Maestro Pizza — System Configuration
Admin-editable parameters. Persisted to JSON.
"""
from dataclasses import dataclass
import json, os

CONFIG_PATH = "config.json"

USERS = {
    "admin": {"password": "DailyFood@2026", "role": "admin"},
    "subham": {"password": "delivery123", "role": "admin"},
    "user": {"password": "maestro2026", "role": "user"},
}

@dataclass
class AppConfig:
    ga_population: int = 100
    ga_generations: int = 60
    penalty_5d: float = 26.44
    penalty_6d: float = 22.04
    mc_threshold_primary: float = 0.8
    mc_threshold_fallback: float = 0.6
    mc_max_default: int = 3
    mc_min_shift: int = 8
    mc_max_shift: int = 12
    mc_capacity_threshold: float = 2.25
    mc_ttb_threshold: float = 9.0
    poly_penalty_per_order: float = 3.25
    poly_penalty_cap_threshold: float = 2.25
    cost_3p_per_order: float = 14.75
    cost_staff_per_hour: float = 0.0
    cost_variable_per_order: float = 6.0

    def save(self):
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.__dict__, f, indent=2)

    @classmethod
    def load(cls):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            c = cls()
            for k, v in data.items():
                if hasattr(c, k): setattr(c, k, v)
            return c
        return cls()

cfg = AppConfig.load()
