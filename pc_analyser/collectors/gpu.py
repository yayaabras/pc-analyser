"""GPU collector — NVIDIA via nvidia-smi/GPUtil, AMD via sysfs or ADL."""

import os
import subprocess
import shutil


def collect_gpu() -> list[dict]:
    gpus = []
    gpus.extend(_collect_nvidia_smi())
    if not gpus:
        gpus.extend(_collect_nvidia_gputil())
    if not gpus:
        gpus.extend(_collect_amd_sysfs())
    if not gpus:
        gpus.extend(_collect_linux_generic())
    # WSL fallback
    if not gpus:
        from ..wsl_bridge import get_gpu_info, is_wsl
        if is_wsl():
            gpus.extend(get_gpu_info())
    return gpus


# ── NVIDIA via nvidia-smi ─────────────────────────────────────────────────────

def _collect_nvidia_smi() -> list[dict]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        query = (
            "index,name,driver_version,memory.total,memory.used,memory.free,"
            "utilization.gpu,temperature.gpu,fan.speed,"
            "clocks.current.graphics,clocks.current.memory,power.draw"
        )
        out = subprocess.check_output(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            timeout=5, text=True,
        )
        result = []
        for line in out.strip().splitlines():
            p = [x.strip() for x in line.split(",")]
            if len(p) < 12:
                continue
            def _f(v, fb=None):
                try: return float(v)
                except: return fb
            result.append({
                "id": int(p[0]),
                "name": p[1], "driver": p[2], "vendor": "NVIDIA",
                "vram_total_mb": _f(p[3]), "vram_used_mb": _f(p[4]),
                "vram_free_mb": _f(p[5]),
                "load_percent": _f(p[6]),
                "temperature_c": _f(p[7]),
                "fan_speed_percent": _f(p[8]),
                "core_clock_mhz": _f(p[9]),
                "mem_clock_mhz": _f(p[10]),
                "power_draw_w": _f(p[11]),
                "junction_temp_c": None,
                "resolution": None,
            })
        return result
    except Exception:
        return []


# ── NVIDIA via GPUtil ─────────────────────────────────────────────────────────

def _collect_nvidia_gputil() -> list[dict]:
    try:
        import GPUtil
        result = []
        for g in GPUtil.getGPUs():
            result.append({
                "id": g.id, "name": g.name, "driver": g.driver, "vendor": "NVIDIA",
                "vram_total_mb": round(g.memoryTotal, 1),
                "vram_used_mb": round(g.memoryUsed, 1),
                "vram_free_mb": round(g.memoryFree, 1),
                "load_percent": round(g.load * 100, 1),
                "temperature_c": g.temperature,
                "fan_speed_percent": None,
                "core_clock_mhz": None, "mem_clock_mhz": None,
                "power_draw_w": None, "junction_temp_c": None,
                "resolution": None,
            })
        return result
    except Exception:
        return []


# ── AMD via sysfs (Linux / WSL with amdgpu driver) ───────────────────────────

def _collect_amd_sysfs() -> list[dict]:
    """
    Read AMD GPU data directly from /sys/class/drm/cardN/device/.
    Works on Linux with amdgpu driver loaded.
    """
    drm = "/sys/class/drm"
    if not os.path.exists(drm):
        return []

    result = []
    idx = 0

    for card in sorted(os.listdir(drm)):
        if not card.startswith("card") or "render" in card or "-" in card:
            continue
        base = os.path.join(drm, card, "device")
        vendor_file = os.path.join(base, "vendor")
        if not os.path.exists(vendor_file):
            continue
        try:
            vendor_id = open(vendor_file).read().strip()
        except OSError:
            continue
        if vendor_id != "0x1002":  # AMD only
            continue

        gpu: dict = {
            "id": idx, "vendor": "AMD", "driver": "amdgpu",
            "name": "AMD GPU", "driver_version": None,
            "vram_total_mb": None, "vram_used_mb": None, "vram_free_mb": None,
            "load_percent": None, "temperature_c": None, "junction_temp_c": None,
            "fan_speed_percent": None, "fan_rpm": None,
            "core_clock_mhz": None, "mem_clock_mhz": None,
            "power_draw_w": None, "resolution": None,
        }

        # GPU name from uevent
        uevent = os.path.join(base, "uevent")
        try:
            for line in open(uevent):
                if "DRIVER=" in line:
                    gpu["driver"] = line.split("=")[1].strip()
                if "PCI_ID=" in line:
                    gpu["name"] = f"AMD GPU ({line.split('=')[1].strip()})"
        except OSError:
            pass

        # GPU utilisation
        gpu["load_percent"] = _sysfs_int(os.path.join(base, "gpu_busy_percent"))

        # VRAM
        vram_total = _sysfs_int(os.path.join(base, "mem_info_vram_total"))
        vram_used = _sysfs_int(os.path.join(base, "mem_info_vram_used"))
        if vram_total:
            gpu["vram_total_mb"] = round(vram_total / 1024 ** 2, 1)
        if vram_used:
            gpu["vram_used_mb"] = round(vram_used / 1024 ** 2, 1)
        if vram_total and vram_used:
            gpu["vram_free_mb"] = round((vram_total - vram_used) / 1024 ** 2, 1)

        # Clocks
        pp_clk = os.path.join(base, "pp_dpm_sclk")
        pp_mclk = os.path.join(base, "pp_dpm_mclk")
        gpu["core_clock_mhz"] = _parse_amd_clock(pp_clk)
        gpu["mem_clock_mhz"] = _parse_amd_clock(pp_mclk)

        # Hwmon (temp, power, fan)
        hwmon_dir = os.path.join(base, "hwmon")
        if os.path.exists(hwmon_dir):
            for hwmon in os.listdir(hwmon_dir):
                hpath = os.path.join(hwmon_dir, hwmon)
                # Temperatures
                for tfile in sorted(os.listdir(hpath)) if os.path.exists(hpath) else []:
                    if tfile.startswith("temp") and tfile.endswith("_input"):
                        raw = _sysfs_int(os.path.join(hpath, tfile))
                        label_file = os.path.join(hpath, tfile.replace("_input", "_label"))
                        label = ""
                        try:
                            label = open(label_file).read().strip().lower()
                        except OSError:
                            pass
                        if raw:
                            temp_c = round(raw / 1000, 1)
                            if "junction" in label or "hotspot" in label:
                                gpu["junction_temp_c"] = temp_c
                            elif gpu["temperature_c"] is None:
                                gpu["temperature_c"] = temp_c

                # Power
                power_raw = _sysfs_int(os.path.join(hpath, "power1_average"))
                if power_raw:
                    gpu["power_draw_w"] = round(power_raw / 1_000_000, 1)

                # Fan
                fan_input = _sysfs_int(os.path.join(hpath, "fan1_input"))
                fan_max = _sysfs_int(os.path.join(hpath, "fan1_max"))
                if fan_input:
                    gpu["fan_rpm"] = fan_input
                    if fan_max and fan_max > 0:
                        gpu["fan_speed_percent"] = round(fan_input / fan_max * 100, 1)
                break

        result.append(gpu)
        idx += 1

    return result


# ── Generic Linux (Intel / other) ────────────────────────────────────────────

def _collect_linux_generic() -> list[dict]:
    drm = "/sys/class/drm"
    if not os.path.exists(drm):
        return []
    result = []
    seen = set()
    try:
        for card in sorted(os.listdir(drm)):
            if not card.startswith("card") or "-" in card:
                continue
            vendor_file = os.path.join(drm, card, "device", "vendor")
            if not os.path.exists(vendor_file):
                continue
            vid = open(vendor_file).read().strip()
            if vid in seen:
                continue
            seen.add(vid)
            vendor = {"0x1002": "AMD", "0x10de": "NVIDIA", "0x8086": "Intel"}.get(vid, vid)
            result.append({
                "id": len(result), "name": f"{vendor} GPU", "vendor": vendor,
                "driver": None, "vram_total_mb": None, "vram_used_mb": None,
                "vram_free_mb": None, "load_percent": None, "temperature_c": None,
                "junction_temp_c": None, "fan_speed_percent": None, "fan_rpm": None,
                "core_clock_mhz": None, "mem_clock_mhz": None,
                "power_draw_w": None, "resolution": None,
            })
    except Exception:
        pass
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sysfs_int(path: str):
    try:
        return int(open(path).read().strip())
    except (OSError, ValueError):
        return None


def _parse_amd_clock(path: str):
    """Parse pp_dpm_sclk — return current clock in MHz (line marked with *)."""
    try:
        for line in open(path):
            if "*" in line:
                # Format: "2: 2615Mhz *"
                parts = line.strip().split()
                for p in parts:
                    mhz = p.upper().replace("MHZ", "").replace("*", "").strip()
                    try:
                        return float(mhz)
                    except ValueError:
                        continue
    except OSError:
        pass
    return None
