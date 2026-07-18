"""Storage collector — partitions, usage, I/O stats, SMART health."""

import shutil
import subprocess
import psutil


def collect_storage() -> list[dict]:
    """Return a list of dicts, one per physical disk partition."""
    disks = []

    # I/O counters
    try:
        io_counters = psutil.disk_io_counters(perdisk=True)
    except Exception:
        io_counters = {}

    seen_devices = set()
    for part in psutil.disk_partitions(all=False):
        device = part.device
        if device in seen_devices:
            continue
        seen_devices.add(device)

        disk = {
            "device": device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "total_gb": None,
            "used_gb": None,
            "free_gb": None,
            "usage_percent": None,
            "read_mb": None,
            "write_mb": None,
            "smart_health": None,
            "smart_temperature_c": None,
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

        # I/O
        short_device = device.split("/")[-1].split("\\")[-1]
        for key in (short_device, device):
            if key in io_counters:
                io = io_counters[key]
                disk["read_mb"] = round(io.read_bytes / 1024 ** 2, 1)
                disk["write_mb"] = round(io.write_bytes / 1024 ** 2, 1)
                break

        # SMART
        smart = _get_smart_health(device)
        disk["smart_health"] = smart.get("health")
        disk["smart_temperature_c"] = smart.get("temperature_c")

        disks.append(disk)

    return disks


def _get_smart_health(device: str) -> dict:
    """Run smartctl to get drive health and temperature."""
    if not shutil.which("smartctl"):
        return {}
    try:
        result = subprocess.run(
            ["smartctl", "-H", "-A", device],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout + result.stderr
        health = None
        temp = None

        for line in output.splitlines():
            line_lower = line.lower()
            if "smart overall-health" in line_lower or "smart health status" in line_lower:
                if "passed" in line_lower or "ok" in line_lower:
                    health = "PASSED"
                elif "failed" in line_lower:
                    health = "FAILED"
            # Temperature_Celsius attribute
            if "temperature_celsius" in line_lower or "airflow_temperature_cel" in line_lower:
                parts = line.split()
                for i, p in enumerate(parts):
                    try:
                        val = int(p)
                        if 0 < val < 100:
                            temp = val
                            break
                    except ValueError:
                        continue

        return {"health": health, "temperature_c": temp}
    except Exception:
        return {}
