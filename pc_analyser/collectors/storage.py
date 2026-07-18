"""Disk collector — usage, IOPS/throughput deltas, full SMART attributes."""

import shutil
import subprocess
import time
import psutil


def collect_storage() -> list[dict]:
    disks = []

    # On WSL/Windows — use PowerShell for physical disk details
    from ..wsl_bridge import is_wsl, get_disk_info, get_disk_smart_windows
    if is_wsl():
        win_disks = get_disk_info()
        # Enrich with SMART data per disk
        for d in win_disks:
            smart = get_disk_smart_windows(d["index"])
            d.update(smart)
        if win_disks:
            # Also get mount/usage from psutil and merge
            _merge_psutil_usage(win_disks)
            return win_disks

    # Native Linux path
    io1 = _get_io_counters()
    time.sleep(0.5)
    io2 = _get_io_counters()
    dt = 0.5

    seen_devices = set()
    for part in psutil.disk_partitions(all=False):
        device = part.device
        if device in seen_devices:
            continue
        seen_devices.add(device)

        disk: dict = {
            "device": device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "total_gb": None,
            "used_gb": None,
            "free_gb": None,
            "usage_percent": None,
            # Cumulative I/O
            "read_mb_total": None,
            "write_mb_total": None,
            # Live IOPS / throughput
            "read_iops": None,
            "write_iops": None,
            "read_mb_per_sec": None,
            "write_mb_per_sec": None,
            # SMART
            "smart_health": None,
            "smart_temperature_c": None,
            "smart_power_on_hours": None,
            "smart_reallocated_sectors": None,
            "smart_wear_level": None,
        }

        # Usage
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk["total_gb"] = round(usage.total / 1024 ** 3, 2)
            disk["used_gb"] = round(usage.used / 1024 ** 3, 2)
            disk["free_gb"] = round(usage.free / 1024 ** 3, 2)
            disk["usage_percent"] = usage.percent
        except (PermissionError, OSError):
            pass

        # I/O stats
        short = device.split("/")[-1].split("\\")[-1]
        for key in (short, device):
            c1 = io1.get(key)
            c2 = io2.get(key)
            if c1 and c2:
                disk["read_mb_total"] = round(c2.read_bytes / 1024 ** 2, 1)
                disk["write_mb_total"] = round(c2.write_bytes / 1024 ** 2, 1)
                disk["read_iops"] = round((c2.read_count - c1.read_count) / dt)
                disk["write_iops"] = round((c2.write_count - c1.write_count) / dt)
                disk["read_mb_per_sec"] = round(
                    (c2.read_bytes - c1.read_bytes) / dt / 1024 ** 2, 2)
                disk["write_mb_per_sec"] = round(
                    (c2.write_bytes - c1.write_bytes) / dt / 1024 ** 2, 2)
                break

        # SMART
        smart = _get_smart(device)
        disk.update(smart)
        disks.append(disk)

    return disks


def _merge_psutil_usage(win_disks: list) -> None:
    """Add mount point and usage % to Windows disk list from psutil."""
    try:
        vol_usage = {}
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                letter = part.mountpoint.replace("\\", "").replace("/", "").upper().rstrip(":")
                vol_usage[letter] = {
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / 1024 ** 3, 2),
                    "used_gb": round(usage.used / 1024 ** 3, 2),
                    "free_gb": round(usage.free / 1024 ** 3, 2),
                    "usage_percent": usage.percent,
                }
            except Exception:
                pass
        for d in win_disks:
            vols = d.get("volumes", [])
            for v in vols:
                letter = str(v).upper().rstrip(":")
                if letter in vol_usage:
                    d.update(vol_usage[letter])
                    break
    except Exception:
        pass
    try:
        return psutil.disk_io_counters(perdisk=True) or {}
    except Exception:
        return {}


def _get_smart(device: str) -> dict:
    if not shutil.which("smartctl"):
        return {}
    try:
        result = subprocess.run(
            ["smartctl", "-H", "-A", "-i", device],
            capture_output=True, text=True, timeout=6,
        )
        output = result.stdout + result.stderr
        data = {
            "smart_health": None,
            "smart_temperature_c": None,
            "smart_power_on_hours": None,
            "smart_reallocated_sectors": None,
            "smart_wear_level": None,
        }

        for line in output.splitlines():
            ll = line.lower()

            if "smart overall-health" in ll or "smart health status" in ll:
                data["smart_health"] = "PASSED" if "passed" in ll or "ok" in ll else "FAILED"

            if "temperature_celsius" in ll or "airflow_temperature_cel" in ll:
                data["smart_temperature_c"] = _extract_smart_val(line)

            if "power_on_hours" in ll:
                data["smart_power_on_hours"] = _extract_smart_val(line)

            if "reallocated_sector" in ll:
                data["smart_reallocated_sectors"] = _extract_smart_val(line)

            if "wear_leveling_count" in ll or "percent_lifetime_remain" in ll:
                data["smart_wear_level"] = _extract_smart_val(line)

        return data
    except Exception:
        return {}


def _extract_smart_val(line: str):
    """Extract the raw value integer from a smartctl attribute line."""
    parts = line.split()
    # smartctl attr lines: ID# ATTRIBUTE_NAME FLAG VALUE WORST THRESH TYPE UPDATED WHEN_FAILED RAW_VALUE
    # RAW_VALUE is last, but might have extra info — grab last numeric token
    for p in reversed(parts):
        try:
            v = int(p.split("+")[0].split("h")[0])
            if 0 <= v < 10_000_000:
                return v
        except ValueError:
            continue
    return None
