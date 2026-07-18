"""Rich terminal display — render all hardware data as formatted tables."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

console = Console()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _bar(value, unit=""):
    if value is None:
        return "N/A"
    v = float(value)
    color = "green" if v < 70 else "yellow" if v < 90 else "red"
    filled = int(v / 5)
    bar = "█" * filled + "░" * (20 - filled)
    return f"[{color}]{bar}[/{color}] {v:.1f}{unit}"


def _mhz(value):
    if value is None:
        return "N/A"
    if float(value) >= 1000:
        return f"{float(value) / 1000:.2f} GHz"
    return f"{float(value):.0f} MHz"


def _kb(value):
    if value is None:
        return "N/A"
    if int(value) >= 1024:
        return f"{int(value) / 1024:.1f} MB"
    return f"{value} KB"


# ── Header ────────────────────────────────────────────────────────────────────

def render_header(live=False):
    subtitle = "live monitor  [dim](Ctrl+C to exit)[/dim]" if live else "hardware snapshot"
    return Panel(f"[bold cyan]PC Analyser[/bold cyan] — {subtitle}", box=box.DOUBLE)


# ── Alerts ────────────────────────────────────────────────────────────────────

def render_alerts(alerts):
    if not alerts:
        return None
    text = Text()
    for a in alerts:
        color = "bold red" if a.severity == "critical" else "bold yellow"
        text.append(f"  {a}\n", style=color)
    return Panel(text, title="[bold red]  Alerts[/bold red]", border_style="red")


# ── CPU ───────────────────────────────────────────────────────────────────────

def render_cpu(cpu):
    t = Table(box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Property", style="cyan", no_wrap=True)
    t.add_column("Value", style="white")
    t.add_row("Model", cpu.get("model") or "N/A")
    t.add_row("Architecture", cpu.get("architecture") or "N/A")
    t.add_row("Vendor", cpu.get("vendor") or "N/A")
    t.add_row("Physical Cores", str(cpu.get("physical_cores", "N/A")))
    t.add_row("Logical Cores", str(cpu.get("logical_cores", "N/A")))
    t.add_row("Usage", _bar(cpu.get("usage_percent"), "%"))
    t.add_row("Frequency", _mhz(cpu.get("frequency_mhz")))
    t.add_row("Freq Min / Max",
              f"{_mhz(cpu.get('frequency_min_mhz'))} / {_mhz(cpu.get('frequency_max_mhz'))}")
    t.add_row("L2 Cache", _kb(cpu.get("cache_l2_kb")))
    t.add_row("L3 Cache", _kb(cpu.get("cache_l3_kb")))
    per_core = cpu.get("per_core_usage", [])
    if per_core:
        cores_str = "  ".join(
            f"[{'green' if v < 70 else 'yellow' if v < 90 else 'red'}]C{i}:{v:.0f}%[/]"
            for i, v in enumerate(per_core)
        )
        t.add_row("Per-Core Usage", cores_str)
    return Panel(t, title="[bold green]CPU[/bold green]", border_style="green")


# ── Memory ────────────────────────────────────────────────────────────────────

def render_memory(mem):
    t = Table(box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Property", style="cyan", no_wrap=True)
    t.add_column("Value", style="white")
    t.add_row("Total RAM", f"{mem.get('total_gb', 'N/A')} GB")
    t.add_row("Used", f"{mem.get('used_gb', 'N/A')} GB")
    t.add_row("Available", f"{mem.get('available_gb', 'N/A')} GB")
    t.add_row("Usage", _bar(mem.get("usage_percent"), "%"))
    t.add_row("RAM Type", mem.get("type") or "N/A")
    speed = mem.get("speed_mhz")
    t.add_row("Speed", f"{speed} MHz" if speed else "N/A")
    t.add_row("Slots Used / Total",
              f"{mem.get('slots_used', 'N/A')} / {mem.get('slots_total', 'N/A')}")
    t.add_row("Swap Total", f"{mem.get('swap_total_gb', 0)} GB")
    t.add_row("Swap Used", _bar(mem.get("swap_percent"), "%"))
    for i, s in enumerate(mem.get("sticks", [])):
        t.add_row(
            f"  Stick {i + 1}",
            f"{s['size_gb']} GB  {s.get('type', '')}  "
            f"{s.get('speed_mhz') or ''}MHz  [{s.get('manufacturer', '')}]  {s.get('part_number', '')}",
        )
    return Panel(t, title="[bold blue]Memory (RAM)[/bold blue]", border_style="blue")


# ── Thermal & Fans ────────────────────────────────────────────────────────────

def render_thermal(thermal):
    t = Table(box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Sensor", style="cyan", no_wrap=True)
    t.add_column("Label", style="white")
    t.add_column("Temp (C)", style="white", justify="right")
    t.add_column("High", style="yellow", justify="right")
    t.add_column("Critical", style="red", justify="right")
    for sensor, entries in thermal.get("temperatures", {}).items():
        for e in entries:
            val = e["current_c"]
            color = "green" if val < 60 else "yellow" if val < 80 else "red"
            t.add_row(
                sensor, e["label"],
                f"[{color}]{val}[/{color}]",
                str(e["high_c"] or "-"),
                str(e["critical_c"] or "-"),
            )
    if not thermal.get("temperatures"):
        t.add_row("-", "No sensor data available", "-", "-", "-")

    fans_t = Table(box=box.SIMPLE_HEAVY, expand=True)
    fans_t.add_column("Fan", style="cyan")
    fans_t.add_column("Label", style="white")
    fans_t.add_column("RPM", style="white", justify="right")
    for fan, entries in thermal.get("fans", {}).items():
        for e in entries:
            fans_t.add_row(fan, e["label"], str(e["rpm"]))

    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(t)
    if thermal.get("fans"):
        grid.add_row(Panel(fans_t, title="Fans", border_style="dim"))
    return Panel(grid, title="[bold yellow]Temperatures & Fans[/bold yellow]", border_style="yellow")


# ── GPU ───────────────────────────────────────────────────────────────────────

def render_gpu(gpus):
    t = Table(box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Property", style="cyan", no_wrap=True)
    t.add_column("Value", style="white")
    if not gpus:
        t.add_row("Status", "No GPU detected / nvidia-smi not available")
    else:
        for i, g in enumerate(gpus):
            if i > 0:
                t.add_row("", "")
            t.add_row(f"GPU {i}", g.get("name", "Unknown"))
            t.add_row("  Vendor", g.get("vendor") or "N/A")
            t.add_row("  Driver", g.get("driver") or "N/A")
            vt = g.get("vram_total_mb")
            vu = g.get("vram_used_mb")
            t.add_row("  VRAM", f"{vu} / {vt} MB" if vt else "N/A")
            t.add_row("  Load", _bar(g.get("load_percent"), "%"))
            t.add_row("  Temperature", f"{g.get('temperature_c', 'N/A')} C")
            fan = g.get("fan_speed_percent")
            t.add_row("  Fan Speed", f"{fan}%" if fan is not None else "N/A")
    return Panel(t, title="[bold magenta]GPU[/bold magenta]", border_style="magenta")


# ── Storage ───────────────────────────────────────────────────────────────────

def render_storage(disks):
    t = Table(box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Device", style="cyan", no_wrap=True)
    t.add_column("Mount", style="white")
    t.add_column("FS", style="dim")
    t.add_column("Total", justify="right")
    t.add_column("Used", justify="right")
    t.add_column("Free", justify="right")
    t.add_column("Usage", justify="right")
    t.add_column("Read MB", justify="right")
    t.add_column("Write MB", justify="right")
    t.add_column("SMART", justify="center")
    t.add_column("Disk C", justify="right")
    if not disks:
        t.add_row("-", "No disks found", "", "", "", "", "", "", "", "", "")
    for d in disks:
        pct = d.get("usage_percent")
        pc = "green" if (pct or 0) < 70 else "yellow" if (pct or 0) < 90 else "red"
        smart = d.get("smart_health") or "-"
        sc = "green" if smart == "PASSED" else "red" if smart == "FAILED" else "dim"
        t.add_row(
            d.get("device", "?"), d.get("mountpoint", "?"), d.get("fstype", "?"),
            f"{d.get('total_gb', '?')} GB", f"{d.get('used_gb', '?')} GB",
            f"{d.get('free_gb', '?')} GB", f"[{pc}]{pct or '?'}%[/{pc}]",
            f"{d.get('read_mb', '?')} MB", f"{d.get('write_mb', '?')} MB",
            f"[{sc}]{smart}[/{sc}]", str(d.get("smart_temperature_c") or "-"),
        )
    return Panel(t, title="[bold white]Storage[/bold white]", border_style="white")


# ── Network ───────────────────────────────────────────────────────────────────

def render_network(ifaces):
    t = Table(box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Interface", style="cyan", no_wrap=True)
    t.add_column("Status", justify="center")
    t.add_column("IPv4", style="white")
    t.add_column("MAC", style="dim")
    t.add_column("Speed", justify="right")
    t.add_column("Up KB/s", justify="right")
    t.add_column("Down KB/s", justify="right")
    t.add_column("Sent MB", justify="right")
    t.add_column("Recv MB", justify="right")
    for iface in ifaces:
        status = "[green]UP[/green]" if iface.get("is_up") else "[red]DOWN[/red]"
        speed = iface.get("speed_mbps")
        t.add_row(
            iface.get("name", "?"), status,
            iface.get("ipv4") or "-", iface.get("mac") or "-",
            f"{speed} Mbps" if speed else "-",
            str(iface.get("send_rate_kbps") or "-"),
            str(iface.get("recv_rate_kbps") or "-"),
            str(iface.get("bytes_sent_mb") or "-"),
            str(iface.get("bytes_recv_mb") or "-"),
        )
    return Panel(t, title="[bold cyan]Network[/bold cyan]", border_style="cyan")


# ── Battery ───────────────────────────────────────────────────────────────────

def render_battery(bat):
    if not bat:
        return None
    pct = bat.get("percent", 0)
    color = "green" if pct > 50 else "yellow" if pct > 20 else "red"
    text = (
        f"[{color}]{pct}%[/{color}]  |  "
        f"Status: {bat.get('status', 'N/A')}  |  "
        f"Time remaining: {bat.get('time_remaining') or 'N/A'}"
    )
    return Panel(text, title="[bold green]Battery[/bold green]", border_style="green")


# ── Motherboard ───────────────────────────────────────────────────────────────

def render_motherboard(mobo):
    t = Table(box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Property", style="cyan", no_wrap=True)
    t.add_column("Value", style="white")
    t.add_row("Manufacturer", mobo.get("manufacturer") or "N/A")
    t.add_row("Product", mobo.get("product") or "N/A")
    t.add_row("Version", mobo.get("version") or "N/A")
    t.add_row("Serial", mobo.get("serial") or "N/A")
    t.add_row("BIOS Vendor", mobo.get("bios_vendor") or "N/A")
    t.add_row("BIOS Version", mobo.get("bios_version") or "N/A")
    t.add_row("BIOS Date", mobo.get("bios_date") or "N/A")
    return Panel(t, title="[bold dim]Motherboard / BIOS[/bold dim]", border_style="dim")


# ── Full snapshot render ──────────────────────────────────────────────────────

def render_snapshot(data: dict, alerts: list) -> None:
    console.print(render_header(live=False))
    alert_panel = render_alerts(alerts)
    if alert_panel:
        console.print(alert_panel)
    console.print(render_cpu(data.get("cpu", {})))
    console.print(render_memory(data.get("memory", {})))
    console.print(render_thermal(data.get("thermal", {})))
    console.print(render_gpu(data.get("gpu", [])))
    console.print(render_storage(data.get("storage", [])))
    console.print(render_network(data.get("network", [])))
    bat = render_battery(data.get("battery"))
    if bat:
        console.print(bat)
    console.print(render_motherboard(data.get("motherboard", {})))


def render_live_frame(data: dict, alerts: list):
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_row(render_header(live=True))
    ap = render_alerts(alerts)
    if ap:
        grid.add_row(ap)
    grid.add_row(render_cpu(data.get("cpu", {})))
    grid.add_row(render_memory(data.get("memory", {})))
    grid.add_row(render_thermal(data.get("thermal", {})))
    grid.add_row(render_gpu(data.get("gpu", [])))
    grid.add_row(render_storage(data.get("storage", [])))
    grid.add_row(render_network(data.get("network", [])))
    bat = render_battery(data.get("battery"))
    if bat:
        grid.add_row(bat)
    grid.add_row(render_motherboard(data.get("motherboard", {})))
    return grid
