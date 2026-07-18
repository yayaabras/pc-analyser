"""GPU collector — model, VRAM, usage, temperature, fan speed."""

import subprocess
import shutil


def collect_gpu() -> list[dict]:
    """Return a list of dicts, one per detected GPU."""
    gpus = []

    # Try NVIDIA via GPUtil
    gpus.extend(_collect_nvidia_gputil())

    # Try nvidia-smi directly as fallback / extra detail
    if not gpus:
        gpus.extend(_collect_nvidia_smi())

    # Try AMD/Intel via sysfs on Linux (basic)
    if not gpus:
        gpus.extend(_collect_linux_generic())

    # WSL fallback — use PowerShell WMI
    if not gpus:
        from ..wsl_bridge import get_gpu_info, is_wsl
        if is_wsl():
            gpus.extend(get_gpu_info())

    return gpus


def _collect_nvidia_gputil() -> list[dict]:
    """Use GPUtil for NVIDIA GPUs."""
    try:
        import GPUtil  # type: ignore
        raw_gpus = GPUtil.getGPUs()
        result = []
        for g in raw_gpus:
            result.append({
                "id": g.id,
                "name": g.name,
                "driver": g.driver,
                "vram_total_mb": round(g.memoryTotal, 1),
                "vram_used_mb": round(g.memoryUsed, 1),
                "vram_free_mb": round(g.memoryFree, 1),
                "load_percent": round(g.load * 100, 1),
                "temperature_c": g.temperature,
                "fan_speed_percent": None,  # GPUtil doesn't expose fan speed
                "vendor": "NVIDIA",
            })
        return result
    except Exception:
        return []


def _collect_nvidia_smi() -> list[dict]:
    """Parse nvidia-smi for detailed NVIDIA GPU stats including fan speed."""
    if not shutil.which("nvidia-smi"):
        return []
    try:
        query = (
            "index,name,driver_version,memory.total,memory.used,memory.free,"
            "utilization.gpu,temperature.gpu,fan.speed"
        )
        out = subprocess.check_output(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            timeout=5,
            text=True,
        )
        result = []
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) < 9:
                continue

            def _safe_float(v, fallback=None):
                try:
                    return float(v)
                except (ValueError, TypeError):
                    return fallback

            result.append({
                "id": int(parts[0]),
                "name": parts[1],
                "driver": parts[2],
                "vram_total_mb": _safe_float(parts[3]),
                "vram_used_mb": _safe_float(parts[4]),
                "vram_free_mb": _safe_float(parts[5]),
                "load_percent": _safe_float(parts[6]),
                "temperature_c": _safe_float(parts[7]),
                "fan_speed_percent": _safe_float(parts[8]),
                "vendor": "NVIDIA",
            })
        return result
    except Exception:
        return []


def _collect_linux_generic() -> list[dict]:
    """Read basic GPU info from /sys on Linux (AMD/Intel/others)."""
    import os
    gpus = []
    drm_path = "/sys/class/drm"
    if not os.path.exists(drm_path):
        return []
    try:
        seen = set()
        for entry in os.listdir(drm_path):
            vendor_path = os.path.join(drm_path, entry, "device", "vendor")
            product_path = os.path.join(drm_path, entry, "device", "uevent")
            if not os.path.exists(vendor_path):
                continue
            with open(vendor_path) as f:
                vendor_id = f.read().strip()
            if vendor_id in seen:
                continue
            seen.add(vendor_id)
            vendor_name = {
                "0x1002": "AMD",
                "0x10de": "NVIDIA",
                "0x8086": "Intel",
            }.get(vendor_id, vendor_id)
            name = vendor_name + " GPU"
            try:
                with open(product_path) as f:
                    for line in f:
                        if line.startswith("DRIVER="):
                            name = f"{vendor_name} ({line.split('=')[1].strip()})"
            except OSError:
                pass
            gpus.append({
                "id": len(gpus),
                "name": name,
                "driver": None,
                "vram_total_mb": None,
                "vram_used_mb": None,
                "vram_free_mb": None,
                "load_percent": None,
                "temperature_c": None,
                "fan_speed_percent": None,
                "vendor": vendor_name,
            })
    except Exception:
        pass
    return gpus
