"""Memory collector — total, used, available, speed, type, slots."""

import platform
import psutil


def collect_memory() -> dict:
    """Return a dict with full RAM information."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()

    result = {
        "total_gb": round(vm.total / 1024 ** 3, 2),
        "used_gb": round(vm.used / 1024 ** 3, 2),
        "available_gb": round(vm.available / 1024 ** 3, 2),
        "usage_percent": vm.percent,
        "swap_total_gb": round(sw.total / 1024 ** 3, 2),
        "swap_used_gb": round(sw.used / 1024 ** 3, 2),
        "swap_percent": sw.percent,
        # Windows-only details (populated below if on Windows)
        "speed_mhz": None,
        "type": None,
        "slots_used": None,
        "slots_total": None,
        "sticks": [],
    }

    if platform.system() == "Windows":
        result.update(_collect_windows_ram_details())

    return result


def _collect_windows_ram_details() -> dict:
    """Use WMI to get RAM speed, type, and slot info on Windows."""
    try:
        import wmi  # type: ignore
        c = wmi.WMI()
        sticks = []
        mem_type_map = {
            20: "DDR", 21: "DDR2", 22: "DDR2 FB-DIMM",
            24: "DDR3", 26: "DDR4", 34: "DDR5",
        }
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

        slots_total = None
        try:
            slots_total = sum(
                1 for slot in c.Win32_PhysicalMemoryArray()
                if slot.MemoryDevices
                for _ in range(int(slot.MemoryDevices))
            )
        except Exception:
            pass

        speeds = [s["speed_mhz"] for s in sticks if s["speed_mhz"]]
        types = [s["type"] for s in sticks if s["type"]]

        return {
            "sticks": sticks,
            "slots_used": len(sticks),
            "slots_total": slots_total,
            "speed_mhz": speeds[0] if speeds else None,
            "type": types[0] if types else None,
        }
    except Exception:
        return {}
