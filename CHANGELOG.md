# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **CPU**: per-core frequency, load average (1/5/15 min), context switches total, interrupts total, iowait %
- **GPU**: AMD sysfs collector reading `gpu_busy_percent`, VRAM, `pp_dpm_sclk/mclk` clocks, hwmon temps (junction + die), power draw (W), fan RPM — works on Linux with `amdgpu` driver
- **GPU**: NVIDIA nvidia-smi now also queries core/memory clocks and power draw (W)
- **Memory**: page faults total from `/proc/vmstat`, top-5 processes by RSS
- **Disk**: live IOPS (read/write ops/sec) and throughput (MB/s) via 0.5s delta; full SMART attributes: power-on hours, reallocated sectors, wear level
- **Network**: errors in/out, drops in/out, packet counts, default gateway detection, ping latency to gateway
- **Processes** (`collectors/processes.py`): top-N by CPU %, RAM (RSS), and disk I/O — new collector
- **System** (`collectors/system.py`): uptime, boot time, OS version, WSL detection, thermal throttle events — new collector
- **SQLite time-series** (`storage.py`): rolling 24h history at 2s intervals, `store_snapshot()`, `query_history()`, `prune_old()`, `get_stats_summary()`; web server stores every broadcast to DB
- **Web API**: `/api/history` and `/api/history/<hours>` endpoints, `/api/stats` summary endpoint

---

## [0.1.2] - 2026-07-18

### Added
- `tui.py` — interactive menu that launches when running `pc-analyser` with no arguments
- Menu options: Snapshot, Live Monitor, Web Dashboard, Config editor, Exit
- Config menu: set individual thresholds, toggle alerts on/off, reset to defaults
- All menu actions return to the main menu after completing (except Exit)

---

## [0.1.1] - 2026-07-18

### Fixed
- `pyproject.toml` build backend corrected from `setuptools.backends.legacy:build` to `setuptools.build_meta` — fixes `pip install -e .` failing with `BackendUnavailable: Cannot import 'setuptools.backends.legacy'`

---

## [0.1.0] - 2026-07-18

### Added

#### Project scaffold
- Initialised repository `yayaabras/pc-analyser`
- `pyproject.toml` with setuptools build system and `pc-analyser` CLI entry point
- `requirements.txt` with pinned dependencies
- Package structure: `pc_analyser/`, `pc_analyser/collectors/`, `pc_analyser/web/`, `tests/`

#### Collectors
- `collectors/cpu.py` — CPU model, architecture, physical/logical cores, per-core usage, frequency (min/max/current), L2/L3 cache via `py-cpuinfo` + `psutil`
- `collectors/memory.py` — RAM total/used/available/swap, RAM speed (MHz), type (DDR4/DDR5), slot count via WMI on Windows
- `collectors/gpu.py` — NVIDIA GPU stats (model, VRAM, load, temperature, fan speed) via `GPUtil` and `nvidia-smi`; basic AMD/Intel detection via `/sys/class/drm` on Linux
- `collectors/thermal.py` — per-sensor temperatures and fan RPMs via `psutil`; LibreHardwareMonitor WMI bridge on Windows
- `collectors/storage.py` — disk partitions, capacity, I/O totals, SMART health and temperature via `smartctl`
- `collectors/network.py` — all network interfaces, IPv4, MAC, link speed, live upload/download rates (KB/s)
- `collectors/battery.py` — charge %, plugged/unplugged status, estimated time remaining
- `collectors/motherboard.py` — board manufacturer, product, BIOS vendor/version/date via WMI (Windows) and `/sys/class/dmi/id` (Linux)
- `collectors/__init__.py` — `collect_all()` aggregator

#### Alert engine
- `alerts.py` — threshold evaluation with `warning` (within 10 units of threshold) and `critical` (at or above threshold) severity levels
- `config.py` — JSON config at `~/.config/pc-analyser/config.json` with default thresholds for CPU temp, CPU usage, RAM usage, GPU temp, GPU usage, disk usage, and battery level

#### CLI
- `cli.py` — Click-based CLI with four commands:
  - `pc-analyser snapshot` — one-time full hardware report
  - `pc-analyser live [--interval N]` — auto-refreshing terminal dashboard using Rich `Live`
  - `pc-analyser web [--port N] [--no-browser]` — launches Flask web server
  - `pc-analyser config show/set/reset` — view and edit alert thresholds

#### Terminal display
- `display.py` — Rich-based rendering: colour-coded tables for all hardware sections, progress bars for usage %, temperature badges (cool/warm/hot), per-core CPU usage strip, alert banners in red/yellow

#### Web dashboard
- `web/server.py` — Flask + Flask-SocketIO server; background thread broadcasts hardware updates every 2 seconds via WebSocket; `/api/snapshot` REST endpoint for initial page load
- `web/templates/index.html` — responsive dark-theme HTML shell
- `web/static/style.css` — dark GitHub-style theme with cards, status badges, progress bars, and responsive grid layout
- `web/static/app.js` — Chart.js rolling history charts for CPU usage, RAM usage, GPU load/temp, and network throughput; live table updates for thermal, storage, network, and battery; alert banners

#### Tests
- `tests/test_all.py` — unit tests for config loading/saving, alert threshold logic (no alerts, warning, critical, disabled), and structural validation of all collector return types and keys

[0.1.0]: https://github.com/yayaabras/pc-analyser/releases/tag/v0.1.0
