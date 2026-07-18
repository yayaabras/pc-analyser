"""Interactive TUI menu — arrow-key navigable main menu for PC Analyser."""

import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich import box

console = Console()

MENU_ITEMS = [
    ("1", "Snapshot",       "Full hardware report — all details at once"),
    ("2", "Live Monitor",   "Auto-refreshing terminal dashboard (like htop)"),
    ("3", "Web Dashboard",  "Live charts in your browser"),
    ("4", "Config",         "View and edit alert thresholds"),
    ("5", "Exit",           "Quit PC Analyser"),
]


def _render_menu(title="PC Analyser") -> Panel:
    t = Table(box=box.SIMPLE, show_header=False, expand=True, padding=(0, 2))
    t.add_column("Key",  style="bold cyan",  no_wrap=True, width=4)
    t.add_column("Name", style="bold white", no_wrap=True, width=18)
    t.add_column("Description", style="dim")

    for key, name, desc in MENU_ITEMS:
        t.add_row(f"[{key}]", name, desc)

    return Panel(
        t,
        title=f"[bold cyan]{title}[/bold cyan]",
        subtitle="[dim]Type a number and press Enter[/dim]",
        border_style="cyan",
        box=box.DOUBLE,
        padding=(1, 2),
    )


def _config_menu():
    from .config import load_config, set_threshold, save_config, DEFAULT_CONFIG

    while True:
        console.clear()
        cfg = load_config()
        t = Table(box=box.SIMPLE_HEAVY, show_header=True)
        t.add_column("Key", style="cyan")
        t.add_column("Current Value", style="white", justify="right")
        t.add_column("Unit", style="dim")

        for k, v in cfg["thresholds"].items():
            unit = "C" if "temp" in k else "%"
            t.add_row(k, str(v), unit)

        console.print(Panel(t, title="[bold cyan]Alert Thresholds[/bold cyan]",
                            border_style="cyan"))
        console.print(f"  alerts_enabled: [bold]{cfg['alerts_enabled']}[/bold]")
        console.print(f"  refresh_interval: [bold]{cfg['refresh_interval_seconds']}s[/bold]")
        console.print(f"  web_port: [bold]{cfg['web_port']}[/bold]\n")

        console.print("  [cyan][s][/cyan] Set a threshold  "
                      "[cyan][t][/cyan] Toggle alerts  "
                      "[cyan][r][/cyan] Reset to defaults  "
                      "[cyan][b][/cyan] Back\n")

        choice = Prompt.ask("  Option", choices=["s", "t", "r", "b"], default="b")

        if choice == "b":
            break

        elif choice == "s":
            valid_keys = list(DEFAULT_CONFIG["thresholds"].keys())
            console.print("  Valid keys: " + ", ".join(f"[cyan]{k}[/cyan]" for k in valid_keys))
            key = Prompt.ask("  Threshold key")
            if key not in valid_keys:
                console.print(f"[red]Unknown key '{key}'[/red]")
                time.sleep(1.5)
                continue
            val = Prompt.ask(f"  New value for {key}")
            try:
                set_threshold(key, float(val))
                console.print(f"[green]Set {key} = {val}[/green]")
            except ValueError:
                console.print("[red]Value must be a number.[/red]")
            time.sleep(1)

        elif choice == "t":
            cfg["alerts_enabled"] = not cfg["alerts_enabled"]
            save_config(cfg)
            state = "enabled" if cfg["alerts_enabled"] else "disabled"
            console.print(f"[green]Alerts {state}.[/green]")
            time.sleep(1)

        elif choice == "r":
            if Confirm.ask("  Reset all thresholds to defaults?"):
                save_config(DEFAULT_CONFIG)
                console.print("[green]Reset to defaults.[/green]")
                time.sleep(1)


def run_interactive():
    """Launch the interactive menu loop."""
    while True:
        console.clear()
        console.print(_render_menu())
        choice = Prompt.ask(
            "  Select",
            choices=["1", "2", "3", "4", "5"],
            default="1",
        )

        if choice == "1":
            console.clear()
            console.print("[dim]Collecting hardware data...[/dim]\n")
            from .collectors import collect_all
            from .alerts import evaluate_alerts
            from .display import render_snapshot
            data = collect_all()
            alerts = evaluate_alerts(data)
            render_snapshot(data, alerts)
            console.print("\n[dim]Press Enter to return to menu...[/dim]")
            input()

        elif choice == "2":
            from .collectors import collect_all
            from .alerts import evaluate_alerts
            from .display import render_live_frame
            from .config import load_config
            cfg = load_config()
            interval = cfg.get("refresh_interval_seconds", 2)
            console.print(f"[dim]Live monitor — refresh every {interval}s. Ctrl+C to stop.[/dim]")
            try:
                with Live(console=console, refresh_per_second=1, screen=True) as live_display:
                    while True:
                        data = collect_all()
                        alerts = evaluate_alerts(data)
                        live_display.update(render_live_frame(data, alerts))
                        time.sleep(interval)
            except KeyboardInterrupt:
                pass

        elif choice == "3":
            from .config import load_config
            import webbrowser, threading
            cfg = load_config()
            port = cfg.get("web_port", 5000)
            url = f"http://localhost:{port}"
            console.print(f"\n[bold cyan]Starting web dashboard at {url}[/bold cyan]")
            console.print("[dim]Press Ctrl+C to stop the server and return to menu.[/dim]\n")
            threading.Timer(1.5, lambda: webbrowser.open(url)).start()
            try:
                from .web.server import create_app
                app, socketio = create_app()
                socketio.run(app, host="0.0.0.0", port=port,
                             debug=False, use_reloader=False)
            except KeyboardInterrupt:
                pass

        elif choice == "4":
            _config_menu()

        elif choice == "5":
            console.print("\n[dim]Goodbye.[/dim]\n")
            sys.exit(0)
