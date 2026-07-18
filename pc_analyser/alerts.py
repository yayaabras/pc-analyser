"""Alert engine — evaluate hardware readings against configured thresholds."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal

from .config import load_config

Severity = Literal["warning", "critical"]


@dataclass
class Alert:
    metric: str
    label: str
    current_value: float
    threshold: float
    severity: Severity
    unit: str = ""

    def __str__(self) -> str:
        return (
            f"[{self.severity.upper()}] {self.label}: "
            f"{self.current_value}{self.unit} "
            f"(threshold: {self.threshold}{self.unit})"
        )


def evaluate_alerts(data: dict) -> list[Alert]:
    cfg = load_config()
    if not cfg.get("alerts_enabled", True):
        return []

    t = cfg["thresholds"]
    alerts: list[Alert] = []

    cpu_temp = data.get("thermal", {}).get("cpu_temp_c")
    if cpu_temp is not None:
        _check(alerts, "cpu_temp_c", "CPU Temperature", cpu_temp, t["cpu_temp_c"], "C", 10)

    cpu_usage = data.get("cpu", {}).get("usage_percent")
    if cpu_usage is not None:
        _check(alerts, "cpu_usage_percent", "CPU Usage", cpu_usage, t["cpu_usage_percent"], "%", 10)

    ram_usage = data.get("memory", {}).get("usage_percent")
    if ram_usage is not None:
        _check(alerts, "ram_usage_percent", "RAM Usage", ram_usage, t["ram_usage_percent"], "%", 10)

    for i, gpu in enumerate(data.get("gpu", [])):
        name = gpu.get("name", f"GPU {i}")
        temp = gpu.get("temperature_c")
        if temp is not None:
            _check(alerts, "gpu_temp_c", f"{name} Temp", temp, t["gpu_temp_c"], "C", 10)
        usage = gpu.get("load_percent")
        if usage is not None:
            _check(alerts, "gpu_usage_percent", f"{name} Usage", usage, t["gpu_usage_percent"], "%", 5)

    for disk in data.get("storage", []):
        pct = disk.get("usage_percent")
        dev = disk.get("device", "Disk")
        if pct is not None:
            _check(alerts, "disk_usage_percent", f"{dev} Usage", pct, t["disk_usage_percent"], "%", 10)

    battery = data.get("battery")
    if battery is not None:
        pct = battery.get("percent", 100)
        plugged = battery.get("plugged_in", True)
        if not plugged:
            low = t["battery_low_percent"]
            if pct <= low:
                sev: Severity = "critical" if pct <= low / 2 else "warning"
                alerts.append(Alert("battery_low_percent", "Battery Level", pct, low, sev, "%"))

    return alerts


def _check(alerts, metric, label, current, threshold, unit, warn_offset):
    warn_threshold = threshold - warn_offset
    if current >= threshold:
        alerts.append(Alert(metric, label, current, threshold, "critical", unit))
    elif current >= warn_threshold:
        alerts.append(Alert(metric, label, current, warn_threshold, "warning", unit))
