"""Tests for collectors, alerts, and config."""

import pytest
from unittest.mock import patch, MagicMock


# ── Config tests ──────────────────────────────────────────────────────────────

def test_load_config_defaults():
    from pc_analyser.config import load_config, DEFAULT_CONFIG
    with patch("pc_analyser.config.config_path") as mock_path:
        mock_path.return_value = MagicMock(exists=lambda: False)
        cfg = load_config()
    assert "thresholds" in cfg
    assert cfg["thresholds"]["cpu_temp_c"] == DEFAULT_CONFIG["thresholds"]["cpu_temp_c"]


def test_set_threshold_valid():
    from pc_analyser.config import set_threshold, load_config, save_config
    with patch("pc_analyser.config.load_config") as mock_load, \
         patch("pc_analyser.config.save_config") as mock_save:
        mock_load.return_value = {
            "thresholds": {"cpu_temp_c": 80},
            "alerts_enabled": True,
            "refresh_interval_seconds": 2,
            "web_port": 5000,
        }
        result = set_threshold("cpu_temp_c", 75)
    assert result is True


def test_set_threshold_invalid():
    from pc_analyser.config import set_threshold
    with patch("pc_analyser.config.load_config") as mock_load:
        mock_load.return_value = {
            "thresholds": {"cpu_temp_c": 80},
            "alerts_enabled": True,
            "refresh_interval_seconds": 2,
            "web_port": 5000,
        }
        result = set_threshold("nonexistent_key", 50)
    assert result is False


# ── Alert tests ───────────────────────────────────────────────────────────────

MOCK_CONFIG = {
    "alerts_enabled": True,
    "thresholds": {
        "cpu_temp_c": 80,
        "cpu_usage_percent": 90,
        "ram_usage_percent": 90,
        "gpu_temp_c": 85,
        "gpu_usage_percent": 95,
        "disk_usage_percent": 90,
        "battery_low_percent": 20,
    },
}


def test_no_alerts_normal_values():
    from pc_analyser.alerts import evaluate_alerts
    with patch("pc_analyser.alerts.load_config", return_value=MOCK_CONFIG):
        data = {
            "cpu": {"usage_percent": 30},
            "memory": {"usage_percent": 50},
            "gpu": [],
            "storage": [],
            "thermal": {"cpu_temp_c": 45, "temperatures": {}, "fans": {}},
            "battery": None,
        }
        alerts = evaluate_alerts(data)
    assert len(alerts) == 0


def test_critical_cpu_temp():
    from pc_analyser.alerts import evaluate_alerts
    with patch("pc_analyser.alerts.load_config", return_value=MOCK_CONFIG):
        data = {
            "cpu": {"usage_percent": 30},
            "memory": {"usage_percent": 50},
            "gpu": [],
            "storage": [],
            "thermal": {"cpu_temp_c": 85, "temperatures": {}, "fans": {}},
            "battery": None,
        }
        alerts = evaluate_alerts(data)
    assert any(a.severity == "critical" and "CPU Temperature" in a.label for a in alerts)


def test_warning_cpu_temp():
    from pc_analyser.alerts import evaluate_alerts
    with patch("pc_analyser.alerts.load_config", return_value=MOCK_CONFIG):
        data = {
            "cpu": {"usage_percent": 30},
            "memory": {"usage_percent": 50},
            "gpu": [],
            "storage": [],
            "thermal": {"cpu_temp_c": 72, "temperatures": {}, "fans": {}},
            "battery": None,
        }
        alerts = evaluate_alerts(data)
    assert any(a.severity == "warning" for a in alerts)


def test_battery_low_alert():
    from pc_analyser.alerts import evaluate_alerts
    with patch("pc_analyser.alerts.load_config", return_value=MOCK_CONFIG):
        data = {
            "cpu": {"usage_percent": 30},
            "memory": {"usage_percent": 50},
            "gpu": [],
            "storage": [],
            "thermal": {"cpu_temp_c": 45, "temperatures": {}, "fans": {}},
            "battery": {"percent": 15, "plugged_in": False, "status": "Discharging"},
        }
        alerts = evaluate_alerts(data)
    assert any("Battery" in a.label for a in alerts)


def test_alerts_disabled():
    from pc_analyser.alerts import evaluate_alerts
    cfg = {**MOCK_CONFIG, "alerts_enabled": False}
    with patch("pc_analyser.alerts.load_config", return_value=cfg):
        data = {
            "cpu": {"usage_percent": 99},
            "memory": {"usage_percent": 99},
            "gpu": [],
            "storage": [],
            "thermal": {"cpu_temp_c": 99, "temperatures": {}, "fans": {}},
            "battery": None,
        }
        alerts = evaluate_alerts(data)
    assert len(alerts) == 0


# ── Collector structure tests ─────────────────────────────────────────────────

def test_cpu_collector_keys():
    from pc_analyser.collectors.cpu import collect_cpu
    result = collect_cpu()
    for key in ("model", "physical_cores", "logical_cores", "usage_percent",
                "frequency_mhz", "architecture"):
        assert key in result, f"Missing key: {key}"


def test_memory_collector_keys():
    from pc_analyser.collectors.memory import collect_memory
    result = collect_memory()
    for key in ("total_gb", "used_gb", "available_gb", "usage_percent"):
        assert key in result, f"Missing key: {key}"
    assert result["total_gb"] > 0


def test_storage_collector_returns_list():
    from pc_analyser.collectors.storage import collect_storage
    result = collect_storage()
    assert isinstance(result, list)
    if result:
        assert "device" in result[0]
        assert "usage_percent" in result[0]


def test_network_collector_returns_list():
    from pc_analyser.collectors.network import collect_network
    result = collect_network()
    assert isinstance(result, list)


def test_battery_collector_none_or_dict():
    from pc_analyser.collectors.battery import collect_battery
    result = collect_battery()
    assert result is None or isinstance(result, dict)
    if isinstance(result, dict):
        assert "percent" in result


def test_gpu_collector_returns_list():
    from pc_analyser.collectors.gpu import collect_gpu
    result = collect_gpu()
    assert isinstance(result, list)


def test_thermal_collector_keys():
    from pc_analyser.collectors.thermal import collect_thermal
    result = collect_thermal()
    assert "temperatures" in result
    assert "fans" in result
    assert "cpu_temp_c" in result


def test_motherboard_collector_keys():
    from pc_analyser.collectors.motherboard import collect_motherboard
    result = collect_motherboard()
    for key in ("manufacturer", "product", "bios_version"):
        assert key in result, f"Missing key: {key}"
