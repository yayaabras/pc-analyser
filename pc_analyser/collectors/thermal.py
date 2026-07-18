"""Thermal and fan collector — temperatures and fan RPMs."""

import platform
import psutil


def collect_thermal() -> dict:
    """Return temperatures and fan speeds from all available sensors."""
    result = {
        "temperatures": {},
        "fans": {},
        "cpu_temp_c": None,
        "lhm_hint": None,
    }

    # psutil sensors (Linux, macOS, some Windows with drivers)
    _collect_psutil_temps(result)
    _collect_psutil_fans(result)

    # Windows: try LibreHardwareMonitor WMI bridge
    if platform.system() == "Windows":
        _collect_windows_lhm(result)

    # WSL: try LHM via PowerShell bridge
    if platform.system() == "Linux":
        from ..wsl_bridge import is_wsl, get_temperatures_and_fans
        if is_wsl():
            lhm = get_temperatures_and_fans()
            if lhm.get("lhm_available"):
                result["temperatures"].update(lhm["temperatures"])
                result["fans"].update(lhm["fans"])
                if lhm.get("cpu_temp_c") is not None:
                    result["cpu_temp_c"] = lhm["cpu_temp_c"]
            else:
                result["lhm_hint"] = (
                    "Install & run LibreHardwareMonitor with WMI enabled "
                    "to see temperatures and fan speeds. "
                    "See: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor"
                )

    # Best-effort CPU temp extraction
    result["cpu_temp_c"] = _extract_cpu_temp(result["temperatures"])

    return result


def _collect_psutil_temps(result: dict) -> None:
    """Populate result['temperatures'] using psutil."""
    try:
        temps = psutil.sensors_temperatures()
        if not temps:
            return
        for sensor_name, entries in temps.items():
            result["temperatures"][sensor_name] = [
                {
                    "label": e.label or sensor_name,
                    "current_c": round(e.current, 1),
                    "high_c": round(e.high, 1) if e.high else None,
                    "critical_c": round(e.critical, 1) if e.critical else None,
                }
                for e in entries
            ]
    except (AttributeError, Exception):
        pass


def _collect_psutil_fans(result: dict) -> None:
    """Populate result['fans'] using psutil."""
    try:
        fans = psutil.sensors_fans()
        if not fans:
            return
        for fan_name, entries in fans.items():
            result["fans"][fan_name] = [
                {
                    "label": e.label or fan_name,
                    "rpm": e.current,
                }
                for e in entries
            ]
    except (AttributeError, Exception):
        pass


def _collect_windows_lhm(result: dict) -> None:
    """
    Try LibreHardwareMonitor WMI bridge for Windows temps and fans.
    Requires LibreHardwareMonitor to be running with WMI enabled.
    """
    try:
        import wmi  # type: ignore
        c = wmi.WMI(namespace=r"root\LibreHardwareMonitor")
        sensors = c.Sensor()
        for s in sensors:
            name = s.Name or "Unknown"
            value = float(s.Value) if s.Value is not None else None
            sensor_type = s.SensorType or ""

            if sensor_type == "Temperature" and value is not None:
                parent = s.Parent or "LHM"
                if parent not in result["temperatures"]:
                    result["temperatures"][parent] = []
                result["temperatures"][parent].append({
                    "label": name,
                    "current_c": round(value, 1),
                    "high_c": None,
                    "critical_c": None,
                })

            elif sensor_type == "Fan" and value is not None:
                parent = s.Parent or "LHM"
                if parent not in result["fans"]:
                    result["fans"][parent] = []
                result["fans"][parent].append({
                    "label": name,
                    "rpm": int(value),
                })
    except Exception:
        pass


def _extract_cpu_temp(temperatures: dict) -> float | None:
    """Try to find the main CPU temperature from the temperatures dict."""
    priority_keys = ["coretemp", "k10temp", "zenpower", "cpu_thermal", "CPU"]
    for key in priority_keys:
        if key in temperatures:
            entries = temperatures[key]
            if entries:
                # Average all core temps
                vals = [e["current_c"] for e in entries if e["current_c"] is not None]
                if vals:
                    return round(sum(vals) / len(vals), 1)
    # Fallback: first available temp
    for entries in temperatures.values():
        for e in entries:
            if e["current_c"] is not None:
                return e["current_c"]
    return None
