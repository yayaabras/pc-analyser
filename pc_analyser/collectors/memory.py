"""Memory collector — total, used, speed, page faults, per-process RSS."""

import platform
import psutil


def collect_memory() -> dict:
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()

    result = {
        "total_gb": round(vm.total / 1024 ** 3, 2),
        "used_gb": round(vm.used / 1024 ** 3, 2),
        "available_gb": round(vm.available / 1024 ** 3, 2),
        "usage_percent": vm.percent,
        "buffers_gb": round(getattr(vm, "buffers", 0) / 1024 ** 3, 2),
        "cached_gb": round(getattr(vm, "cached", 0) / 1024 ** 3, 2),
        "shared_gb": round(getattr(vm, "shared", 0) / 1024 ** 3, 2),
        "slab_gb": round(getattr(vm, "slab", 0) / 1024 ** 3, 2),
        "swap_total_gb": round(sw.total / 1024 ** 3, 2),
        "swap_used_gb": round(sw.used / 1024 ** 3, 2),
        "swap_percent": sw.percent,
        # Windows / WSL extras
        "speed_mhz": None,
        "type": None,
        "slots_used": None,
        "slots_total": None,
        "sticks": [],
        # Page faults
        "page_faults_total": None,
        # Top processes by RSS
        "top_processes_rss": [],
    }

    # Page faults from /proc/vmstat (Linux)
    result["page_faults_total"] = _read_vmstat_pgfault()

    # Top 5 processes by RSS
    result["top_processes_rss"] = _top_by_rss(5)

    # Platform-specific RAM details
    if platform.system() == "Windows":
        result.update(_collect_windows_ram_details())
    elif platform.system() == "Linux":
        from ..wsl_bridge import is_wsl, get_ram_info
        if is_wsl():
            result.update(get_ram_info())

    return result


def _read_vmstat_pgfault() -> int | None:
    """Read total page faults from /proc/vmstat."""
    try:
        with open("/proc/vmstat") as f:
            for line in f:
                if line.startswith("pgfault"):
                    return int(line.split()[1])
    except OSError:
        pass
    return None


def _top_by_rss(n: int) -> list[dict]:
    """Return top N processes sorted by RSS (resident set size)."""
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            mi = p.info.get("memory_info")
            if mi:
                procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "rss_mb": round(mi.rss / 1024 ** 2, 1),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return sorted(procs, key=lambda x: x["rss_mb"], reverse=True)[:n]


def _collect_windows_ram_details() -> dict:
    try:
        import wmi
        c = wmi.WMI()
        mem_type_map = {
            20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
            24: "DDR3", 26: "DDR4", 34: "DDR5",
        }
        sticks = []
        for mem in c.Win32_PhysicalMemory():
            speed = int(mem.Speed) if mem.Speed else None
            mem_type_code = int(mem.MemoryType) if mem.MemoryType else 0
            sticks.append({
                "slot": mem.DeviceLocator or "Unknown",
                "size_gb": round(int(mem.Capacity or 0) / 1024 ** 3, 2),
                "speed_mhz": speed,
                "type": mem_type_map.get(mem_type_code, f"Type {mem_type_code}"),
                "manufacturer": (mem.Manufacturer or "").strip(),
                "part_number": (mem.PartNumber or "").strip(),
            })
        speeds = [s["speed_mhz"] for s in sticks if s["speed_mhz"]]
        types = [s["type"] for s in sticks if s["type"]]
        return {
            "sticks": sticks,
            "slots_used": len(sticks),
            "speed_mhz": speeds[0] if speeds else None,
            "type": types[0] if types else None,
        }
    except Exception:
        return {}
