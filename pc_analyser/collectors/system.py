"""System collector — uptime, boot time, OS info, throttle events."""

import datetime
import os
import platform
import psutil


def collect_system() -> dict:
    boot_ts = psutil.boot_time()
    boot_dt = datetime.datetime.fromtimestamp(boot_ts)
    uptime_secs = (datetime.datetime.now() - boot_dt).total_seconds()

    h = int(uptime_secs // 3600)
    m = int((uptime_secs % 3600) // 60)
    s = int(uptime_secs % 60)

    result = {
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "hostname": platform.node(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "boot_time": boot_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": int(uptime_secs),
        "uptime_human": f"{h}h {m}m {s}s",
        "cpu_throttle_events": _read_throttle_events(),
        "is_wsl": _detect_wsl(),
        "kernel": platform.release(),
    }
    return result


def _read_throttle_events() -> int | None:
    """
    Read thermal throttle events from /sys (Linux only).
    Returns count or None if not available.
    """
    # Try Intel thermal throttle counter
    throttle_paths = [
        "/sys/devices/system/cpu/cpu0/thermal_throttle/core_throttle_count",
        "/sys/devices/system/cpu/cpu0/thermal_throttle/package_throttle_count",
    ]
    for path in throttle_paths:
        try:
            return int(open(path).read().strip())
        except OSError:
            pass

    # Try /proc/acpi/thermal_zone
    try:
        tz_base = "/sys/class/thermal"
        total = 0
        found = False
        for entry in os.listdir(tz_base):
            trip = os.path.join(tz_base, entry, "trip_point_0_type")
            if os.path.exists(trip):
                found = True
        if found:
            return None  # Can detect zones but not event count without root
    except OSError:
        pass

    return None


def _detect_wsl() -> bool:
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False
