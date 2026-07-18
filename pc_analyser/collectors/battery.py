"""Battery collector — charge, status, time remaining, health."""

import psutil


def collect_battery() -> dict | None:
    """Return battery info or None if no battery is present."""
    try:
        bat = psutil.sensors_battery()
    except Exception:
        return None

    if bat is None:
        return None

    secs_left = bat.secsleft
    time_left = None
    if secs_left not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN) and secs_left > 0:
        h = secs_left // 3600
        m = (secs_left % 3600) // 60
        time_left = f"{h}h {m}m"

    return {
        "percent": round(bat.percent, 1),
        "plugged_in": bat.power_plugged,
        "time_remaining": time_left,
        "status": _battery_status(bat),
    }


def _battery_status(bat) -> str:
    if bat.power_plugged:
        if bat.percent >= 99.9:
            return "Full"
        return "Charging"
    return "Discharging"
