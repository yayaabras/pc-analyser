"""Configuration management — load/save alert thresholds."""

import json
import os
from pathlib import Path

DEFAULT_CONFIG = {
    "thresholds": {
        "cpu_temp_c": 80,
        "cpu_usage_percent": 90,
        "ram_usage_percent": 90,
        "gpu_temp_c": 85,
        "gpu_usage_percent": 95,
        "disk_usage_percent": 90,
        "battery_low_percent": 20,
    },
    "alerts_enabled": True,
    "refresh_interval_seconds": 2,
    "web_port": 5000,
}


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(base) / "pc-analyser" / "config.json"


def load_config() -> dict:
    path = config_path()
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    try:
        with open(path) as f:
            user = json.load(f)
        merged = DEFAULT_CONFIG.copy()
        merged["thresholds"].update(user.get("thresholds", {}))
        for key in ("alerts_enabled", "refresh_interval_seconds", "web_port"):
            if key in user:
                merged[key] = user[key]
        return merged
    except Exception:
        return DEFAULT_CONFIG.copy()


def save_config(cfg: dict) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)


def set_threshold(key: str, value: float) -> bool:
    cfg = load_config()
    if key not in cfg["thresholds"]:
        return False
    cfg["thresholds"][key] = value
    save_config(cfg)
    return True
