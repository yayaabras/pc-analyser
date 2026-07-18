"""SQLite time-series storage — rolling history of hardware snapshots."""

import json
import sqlite3
import time
from pathlib import Path

DB_PATH = Path.home() / ".config" / "pc-analyser" / "history.db"
# Keep last N hours of data at 2s intervals
DEFAULT_RETENTION_HOURS = 24


def get_db_path() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def init_db(path: Path | None = None) -> sqlite3.Connection:
    """Create tables if they don't exist."""
    db = sqlite3.connect(str(path or get_db_path()))
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            ts        REAL    NOT NULL,
            cpu_usage REAL,
            cpu_temp  REAL,
            ram_usage REAL,
            gpu_usage REAL,
            gpu_temp  REAL,
            disk_read_mbs  REAL,
            disk_write_mbs REAL,
            net_send_kbs   REAL,
            net_recv_kbs   REAL,
            full_json TEXT
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_ts ON snapshots(ts)")
    db.commit()
    return db


def store_snapshot(data: dict, db: sqlite3.Connection | None = None) -> None:
    """Insert one hardware snapshot into the DB."""
    close_after = db is None
    if db is None:
        db = init_db()

    ts = time.time()
    cpu = data.get("cpu", {})
    thermal = data.get("thermal", {})
    mem = data.get("memory", {})
    gpus = data.get("gpu", [])
    disks = data.get("storage", [])
    nets = data.get("network", [])

    cpu_usage = cpu.get("usage_percent")
    cpu_temp = thermal.get("cpu_temp_c")
    ram_usage = mem.get("usage_percent")
    gpu_usage = gpus[0].get("load_percent") if gpus else None
    gpu_temp = gpus[0].get("temperature_c") if gpus else None

    # Sum real disks (exclude ramdisk/loop)
    real_disks = [d for d in disks if not d.get("device", "").startswith(("/dev/ram", "/dev/loop"))]
    disk_read = sum(d.get("read_mb_per_sec") or 0 for d in real_disks) or None
    disk_write = sum(d.get("write_mb_per_sec") or 0 for d in real_disks) or None

    # Primary active interface
    active_net = next((n for n in nets if n.get("is_up") and n.get("send_rate_kbps") is not None), None)
    net_send = active_net.get("send_rate_kbps") if active_net else None
    net_recv = active_net.get("recv_rate_kbps") if active_net else None

    db.execute("""
        INSERT INTO snapshots
          (ts, cpu_usage, cpu_temp, ram_usage, gpu_usage, gpu_temp,
           disk_read_mbs, disk_write_mbs, net_send_kbs, net_recv_kbs, full_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (ts, cpu_usage, cpu_temp, ram_usage, gpu_usage, gpu_temp,
          disk_read, disk_write, net_send, net_recv,
          json.dumps(data, default=str)))
    db.commit()

    if close_after:
        db.close()


def query_history(
    hours: float = 1.0,
    db: sqlite3.Connection | None = None,
) -> list[dict]:
    """Return rows from the last N hours as list of dicts."""
    close_after = db is None
    if db is None:
        db = init_db()

    since = time.time() - hours * 3600
    rows = db.execute("""
        SELECT ts, cpu_usage, cpu_temp, ram_usage,
               gpu_usage, gpu_temp, disk_read_mbs, disk_write_mbs,
               net_send_kbs, net_recv_kbs
        FROM snapshots WHERE ts >= ? ORDER BY ts ASC
    """, (since,)).fetchall()

    if close_after:
        db.close()

    return [
        {
            "ts": r[0], "cpu_usage": r[1], "cpu_temp": r[2],
            "ram_usage": r[3], "gpu_usage": r[4], "gpu_temp": r[5],
            "disk_read_mbs": r[6], "disk_write_mbs": r[7],
            "net_send_kbs": r[8], "net_recv_kbs": r[9],
        }
        for r in rows
    ]


def prune_old(retention_hours: float = DEFAULT_RETENTION_HOURS,
              db: sqlite3.Connection | None = None) -> None:
    """Delete rows older than retention_hours."""
    close_after = db is None
    if db is None:
        db = init_db()
    cutoff = time.time() - retention_hours * 3600
    db.execute("DELETE FROM snapshots WHERE ts < ?", (cutoff,))
    db.commit()
    if close_after:
        db.close()


def get_stats_summary(db: sqlite3.Connection | None = None) -> dict:
    """Return min/avg/max for key metrics over all stored data."""
    close_after = db is None
    if db is None:
        db = init_db()
    row = db.execute("""
        SELECT
            COUNT(*),
            MIN(ts), MAX(ts),
            AVG(cpu_usage), MAX(cpu_usage),
            AVG(cpu_temp),  MAX(cpu_temp),
            AVG(ram_usage), MAX(ram_usage),
            AVG(gpu_usage), MAX(gpu_usage),
            AVG(gpu_temp),  MAX(gpu_temp)
        FROM snapshots
    """).fetchone()
    if close_after:
        db.close()
    if not row or not row[0]:
        return {}
    return {
        "total_records": row[0],
        "oldest": row[1], "newest": row[2],
        "cpu_usage_avg": round(row[3] or 0, 1), "cpu_usage_max": round(row[4] or 0, 1),
        "cpu_temp_avg": round(row[5] or 0, 1),  "cpu_temp_max": round(row[6] or 0, 1),
        "ram_usage_avg": round(row[7] or 0, 1), "ram_usage_max": round(row[8] or 0, 1),
        "gpu_usage_avg": round(row[9] or 0, 1), "gpu_usage_max": round(row[10] or 0, 1),
        "gpu_temp_avg": round(row[11] or 0, 1), "gpu_temp_max": round(row[12] or 0, 1),
    }
