"""Process collector — top N processes by CPU, RAM, and disk I/O."""

import psutil


def collect_processes(top_n: int = 10) -> dict:
    """Return top processes by CPU, RAM, and disk I/O."""
    # Prime CPU percent measurement
    procs_raw = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info",
                                   "io_counters", "status", "username"]):
        try:
            procs_raw.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    import time; time.sleep(0.3)

    procs = []
    for p in procs_raw:
        try:
            info = p.as_dict(attrs=["pid", "name", "cpu_percent", "memory_info",
                                    "io_counters", "status", "username"])
            mi = info.get("memory_info")
            io = info.get("io_counters")
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "?",
                "status": info.get("status", "?"),
                "username": info.get("username", "?"),
                "cpu_percent": round(info.get("cpu_percent") or 0.0, 1),
                "rss_mb": round(mi.rss / 1024 ** 2, 1) if mi else 0.0,
                "vms_mb": round(mi.vms / 1024 ** 2, 1) if mi else 0.0,
                "disk_read_mb": round(io.read_bytes / 1024 ** 2, 1) if io else None,
                "disk_write_mb": round(io.write_bytes / 1024 ** 2, 1) if io else None,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            pass

    top_cpu = sorted(procs, key=lambda x: x["cpu_percent"], reverse=True)[:top_n]
    top_ram = sorted(procs, key=lambda x: x["rss_mb"], reverse=True)[:top_n]
    top_disk = sorted(
        [p for p in procs if p["disk_read_mb"] is not None],
        key=lambda x: (x["disk_read_mb"] or 0) + (x["disk_write_mb"] or 0),
        reverse=True,
    )[:top_n]

    return {
        "top_cpu": top_cpu,
        "top_ram": top_ram,
        "top_disk": top_disk,
        "total_processes": len(procs),
    }
