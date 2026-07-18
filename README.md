# PC Analyser

A cross-platform Python tool that fetches **every detail about your PC hardware** — CPU, RAM, GPU, storage, fans, temperatures, network, battery, and motherboard — with a rich terminal CLI and a live web dashboard.

---

## Features

- **CPU** — model, cores, threads, clock speed, per-core usage, L2/L3 cache
- **RAM** — total, used, speed (MHz), type (DDR4/DDR5), slot info (Windows)
- **GPU** — model, VRAM, load %, temperature, fan speed (NVIDIA via nvidia-smi)
- **Temperatures** — per-sensor readings with high/critical thresholds
- **Fans** — RPM for every fan (Linux via psutil, Windows via LibreHardwareMonitor)
- **Storage** — all drives, capacity, read/write totals, SMART health and temperature
- **Network** — all interfaces, IP addresses, live upload/download rates
- **Battery** — charge %, status, estimated time remaining
- **Motherboard** — manufacturer, model, BIOS version and date
- **Alert system** — configurable thresholds, warnings and critical alerts
- **CLI snapshot** — instant full hardware report in the terminal
- **Live terminal mode** — auto-refreshing dashboard like `htop`
- **Web dashboard** — live Chart.js charts, history graphs, alert banners
- **Cross-platform** — Windows and Linux (macOS best-effort)

---

## Installation

### Requirements
- Python 3.9 or newer
- `pip`

### Install from source

```bash
git clone https://github.com/yayaabras/pc-analyser.git
cd pc-analyser
pip install -e .
```

The `pc-analyser` command will be available system-wide after installation.

### Windows extra (for RAM speed, fan RPM, deep temps)

Install [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) and enable the WMI server option. This unlocks fan RPM and per-component temperatures on Windows.

---

## Usage

### One-time snapshot

```bash
pc-analyser
# or explicitly:
pc-analyser snapshot
```

### Live terminal monitor (auto-refreshing)

```bash
pc-analyser live
pc-analyser live --interval 1   # refresh every 1 second
```

### Web dashboard

```bash
pc-analyser web
pc-analyser web --port 8080
pc-analyser web --no-browser    # don't auto-open the browser
```

Then open [http://localhost:5000](http://localhost:5000) in your browser.

### View/set alert thresholds

```bash
# Show current config
pc-analyser config show

# Change a threshold
pc-analyser config set cpu_temp_c 75
pc-analyser config set ram_usage_percent 85

# Reset to defaults
pc-analyser config reset
```

### Available threshold keys

| Key | Default | Unit | Description |
|-----|---------|------|-------------|
| `cpu_temp_c` | 80 | °C | CPU temperature warning |
| `cpu_usage_percent` | 90 | % | CPU usage warning |
| `ram_usage_percent` | 90 | % | RAM usage warning |
| `gpu_temp_c` | 85 | °C | GPU temperature warning |
| `gpu_usage_percent` | 95 | % | GPU usage warning |
| `disk_usage_percent` | 90 | % | Disk usage warning |
| `battery_low_percent` | 20 | % | Low battery warning |

Configuration is stored at `~/.config/pc-analyser/config.json`.

---

## Project Structure

```
pc-analyser/
├── pyproject.toml
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── pc_analyser/
│   ├── cli.py              # Click CLI entry point
│   ├── display.py          # Rich terminal rendering
│   ├── alerts.py           # Alert engine
│   ├── config.py           # Config management
│   ├── collectors/
│   │   ├── cpu.py
│   │   ├── memory.py
│   │   ├── gpu.py
│   │   ├── thermal.py
│   │   ├── storage.py
│   │   ├── network.py
│   │   ├── battery.py
│   │   └── motherboard.py
│   └── web/
│       ├── server.py       # Flask + SocketIO server
│       ├── static/
│       │   ├── app.js      # Chart.js live dashboard
│       │   └── style.css
│       └── templates/
│           └── index.html
└── tests/
    └── test_all.py
```

---

## Running Tests

```bash
pip install pytest pytest-mock
pytest tests/ -v
```

---

## Platform Notes

| Feature | Windows | Linux | macOS |
|---------|---------|-------|-------|
| CPU stats | ✅ | ✅ | ✅ |
| RAM speed/type | ✅ (WMI) | ⚠️ N/A | ⚠️ N/A |
| GPU (NVIDIA) | ✅ | ✅ | ✅ |
| Temperatures | ✅ (LHM) | ✅ | ⚠️ limited |
| Fan RPM | ✅ (LHM) | ✅ | ⚠️ limited |
| Storage SMART | ✅ (smartctl) | ✅ (smartctl) | ✅ (smartctl) |
| Battery | ✅ | ✅ | ✅ |
| Motherboard/BIOS | ✅ (WMI) | ✅ (/sys/dmi) | ⚠️ N/A |

---

## License

MIT
