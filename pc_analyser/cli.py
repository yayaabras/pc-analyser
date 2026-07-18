"""CLI entry point — Click commands for snapshot, live, web, and config modes."""

import time
import click
from rich.live import Live
from rich.console import Console

from . import __version__
from .collectors import collect_all
from .alerts import evaluate_alerts
from .display import render_snapshot, render_live_frame
from .config import load_config, set_threshold, DEFAULT_CONFIG

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="pc-analyser")
@click.pass_context
def main(ctx):
    """PC Analyser — monitor every detail of your hardware."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(snapshot)


@main.command()
def snapshot():
    """Take a one-time snapshot of all hardware metrics."""
    console.print("[dim]Collecting hardware data...[/dim]")
    data = collect_all()
    alerts = evaluate_alerts(data)
    render_snapshot(data, alerts)


@main.command()
@click.option("--interval", "-i", default=None, type=float,
              help="Refresh interval in seconds (default from config).")
def live(interval):
    """Live-updating terminal dashboard. Press Ctrl+C to exit."""
    cfg = load_config()
    refresh = interval or cfg.get("refresh_interval_seconds", 2)

    console.print(f"[dim]Starting live monitor (refresh every {refresh}s)...[/dim]")
    try:
        with Live(console=console, refresh_per_second=1, screen=True) as live_display:
            while True:
                data = collect_all()
                alerts = evaluate_alerts(data)
                live_display.update(render_live_frame(data, alerts))
                time.sleep(refresh)
    except KeyboardInterrupt:
        console.print("\n[dim]Exiting live monitor.[/dim]")


@main.command()
@click.option("--port", "-p", default=None, type=int,
              help="Port to run the web server on (default from config).")
@click.option("--no-browser", is_flag=True, default=False,
              help="Do not open the browser automatically.")
def web(port, no_browser):
    """Launch the live web dashboard in your browser."""
    cfg = load_config()
    run_port = port or cfg.get("web_port", 5000)
    url = f"http://localhost:{run_port}"

    if not no_browser:
        import webbrowser
        import threading
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    console.print(f"[bold cyan]PC Analyser Web Dashboard[/bold cyan]")
    console.print(f"  Listening on [link={url}]{url}[/link]")
    console.print("  Press Ctrl+C to stop.\n")

    from .web.server import create_app
    app, socketio = create_app()
    socketio.run(app, host="0.0.0.0", port=run_port, debug=False, use_reloader=False)


@main.group()
def config():
    """View and edit alert thresholds and settings."""
    pass


@config.command(name="show")
def config_show():
    """Show current configuration."""
    from rich.table import Table
    from rich import box
    cfg = load_config()
    t = Table(box=box.SIMPLE_HEAVY)
    t.add_column("Setting", style="cyan")
    t.add_column("Value", style="white")
    t.add_row("alerts_enabled", str(cfg["alerts_enabled"]))
    t.add_row("refresh_interval_seconds", str(cfg["refresh_interval_seconds"]))
    t.add_row("web_port", str(cfg["web_port"]))
    t.add_row("", "")
    for k, v in cfg["thresholds"].items():
        unit = "C" if "temp" in k else "%"
        t.add_row(f"  threshold: {k}", f"{v}{unit}")
    console.print(t)


@config.command(name="set")
@click.argument("key")
@click.argument("value", type=float)
def config_set(key, value):
    """Set a threshold value. E.g.: pc-analyser config set cpu_temp_c 75"""
    if set_threshold(key, value):
        console.print(f"[green]Set {key} = {value}[/green]")
    else:
        valid = list(DEFAULT_CONFIG["thresholds"].keys())
        console.print(f"[red]Unknown threshold '{key}'. Valid keys:[/red]")
        for k in valid:
            console.print(f"  {k}")


@config.command(name="reset")
def config_reset():
    """Reset all thresholds to defaults."""
    from .config import save_config
    save_config(DEFAULT_CONFIG)
    console.print("[green]Configuration reset to defaults.[/green]")
