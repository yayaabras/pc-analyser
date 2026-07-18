"""CPU collector — model, cores, frequency, usage, cache, load avg, context switches."""

import platform
import psutil

try:
    import cpuinfo
    _CPUINFO_AVAILABLE = True
except ImportError:
    _CPUINFO_AVAILABLE = False


def collect_cpu() -> dict:
    """Return a dict with full CPU information."""
    # Sample CPU % twice so per-core is meaningful
    psutil.cpu_percent(interval=None, percpu=True)  # prime
    import time; time.sleep(0.3)

    per_core_usage = psutil.cpu_percent(interval=None, percpu=True)
    total_usage = sum(per_core_usage) / len(per_core_usage) if per_core_usage else 0.0

    # Per-core frequencies
    per_core_freq = []
    try:
        freqs = psutil.cpu_freq(percpu=True)
        per_core_freq = [round(f.current, 1) for f in freqs] if freqs else []
    except Exception:
        pass

    # Global freq fallback
    freq = psutil.cpu_freq()
    freq_current = round(freq.current, 1) if freq else None
    freq_min = round(freq.min, 1) if freq else None
    freq_max = round(freq.max, 1) if freq else None

    # CPU times (for context switches / interrupts)
    times = psutil.cpu_times()
    ctx = psutil.cpu_stats()

    # Load average (Linux/WSL)
    load_avg = None
    try:
        load_avg = [round(x, 2) for x in psutil.getloadavg()]
    except Exception:
        pass

    result = {
        "model": "Unknown",
        "architecture": platform.machine(),
        "physical_cores": psutil.cpu_count(logical=False) or 0,
        "logical_cores": psutil.cpu_count(logical=True) or 0,
        "usage_percent": round(total_usage, 1),
        "per_core_usage": [round(v, 1) for v in per_core_usage],
        "per_core_freq_mhz": per_core_freq,
        "frequency_mhz": freq_current,
        "frequency_min_mhz": freq_min,
        "frequency_max_mhz": freq_max,
        "load_avg_1_5_15": load_avg,
        "context_switches_total": ctx.ctx_switches,
        "interrupts_total": ctx.interrupts,
        "soft_interrupts_total": ctx.soft_interrupts if hasattr(ctx, "soft_interrupts") else None,
        "iowait_percent": round(times.iowait, 2) if hasattr(times, "iowait") else None,
        "cache_l2_kb": None,
        "cache_l3_kb": None,
        "vendor": None,
        "flags": [],
    }

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
        result["model"] = _read_proc_cpu_model()

    # Override cache with lscpu (more accurate in WSL)
    from ..wsl_bridge import get_cpu_cache
    lscpu_cache = get_cpu_cache()
    if lscpu_cache.get("cache_l2_kb"):
        result["cache_l2_kb"] = lscpu_cache["cache_l2_kb"]
    if lscpu_cache.get("cache_l3_kb"):
        result["cache_l3_kb"] = lscpu_cache["cache_l3_kb"]

    return result


def _parse_cache_size(value) -> int:
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
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":")[1].strip()
    except OSError:
        pass
    return platform.processor() or "Unknown"
