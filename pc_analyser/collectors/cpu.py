"""CPU collector — model, cores, frequency, usage, cache."""

import platform
import psutil

try:
    import cpuinfo
    _CPUINFO_AVAILABLE = True
except ImportError:
    _CPUINFO_AVAILABLE = False


def collect_cpu() -> dict:
    """Return a dict with full CPU information."""
    result = {
        "model": "Unknown",
        "architecture": platform.machine(),
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_cores": psutil.cpu_count(logical=True) or 0,
        "usage_percent": psutil.cpu_percent(interval=0.5),
        "per_core_usage": psutil.cpu_percent(interval=0.5, percpu=True),
        "frequency_mhz": None,
        "frequency_min_mhz": None,
        "frequency_max_mhz": None,
        "cache_l2_kb": None,
        "cache_l3_kb": None,
        "vendor": None,
        "flags": [],
    }

    # Frequency
    freq = psutil.cpu_freq()
    if freq:
        result["frequency_mhz"] = round(freq.current, 1)
        result["frequency_min_mhz"] = round(freq.min, 1)
        result["frequency_max_mhz"] = round(freq.max, 1)

    # Detailed info from py-cpuinfo
    if _CPUINFO_AVAILABLE:
        try:
            info = cpuinfo.get_cpu_info()
            result["model"] = info.get("brand_raw", "Unknown")
            result["vendor"] = info.get("vendor_id_raw", None)
            result["flags"] = info.get("flags", [])
            l2 = info.get("l2_cache_size")
            l3 = info.get("l3_cache_size")
            if l2:
                result["cache_l2_kb"] = _parse_cache_size(l2)
            if l3:
                result["cache_l3_kb"] = _parse_cache_size(l3)
        except Exception:
            pass
    else:
        # Fallback: read from /proc/cpuinfo on Linux
        result["model"] = _read_proc_cpu_model()

    return result


def _parse_cache_size(value) -> int:
    """Convert cache size string like '512 KB' or int bytes to KB."""
    if isinstance(value, int):
        return value // 1024
    if isinstance(value, str):
        value = value.strip().upper()
        if "KB" in value:
            return int(value.replace("KB", "").strip())
        if "MB" in value:
            return int(float(value.replace("MB", "").strip()) * 1024)
        try:
            return int(value) // 1024
        except ValueError:
            return 0
    return 0


def _read_proc_cpu_model() -> str:
    """Read CPU model from /proc/cpuinfo (Linux fallback)."""
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":")[1].strip()
    except OSError:
        pass
    return platform.processor() or "Unknown"
