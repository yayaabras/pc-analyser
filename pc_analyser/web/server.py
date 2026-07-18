"""Flask + SocketIO web server — serves the dashboard and streams live data."""

import time
import threading

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO

from ..collectors import collect_all
from ..alerts import evaluate_alerts
from ..config import load_config
from ..storage import init_db, store_snapshot, query_history, prune_old, get_stats_summary


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["SECRET_KEY"] = "pc-analyser-secret"
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    db = init_db()

    # ── REST endpoints ────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/snapshot")
    def api_snapshot():
        data = collect_all()
        alerts = evaluate_alerts(data)
        return jsonify({
            "data": _serialise(data),
            "alerts": [str(a) for a in alerts],
        })

    @app.route("/api/history")
    @app.route("/api/history/<float:hours>")
    def api_history(hours=1.0):
        rows = query_history(hours=hours, db=db)
        return jsonify(rows)

    @app.route("/api/stats")
    def api_stats():
        return jsonify(get_stats_summary(db=db))

    # ── SocketIO events ──────────────────────────────────────────────────────

    @socketio.on("connect")
    def on_connect():
        pass

    @socketio.on("disconnect")
    def on_disconnect():
        pass

    # ── Background broadcast thread ──────────────────────────────────────────

    def _broadcast_loop():
        cfg = load_config()
        interval = cfg.get("refresh_interval_seconds", 2)
        tick = 0
        while True:
            try:
                data = collect_all()
                alerts = evaluate_alerts(data)
                store_snapshot(data, db=db)
                # Prune every 5 minutes
                if tick % (300 // interval) == 0:
                    prune_old(db=db)
                socketio.emit("hardware_update", {
                    "data": _serialise(data),
                    "alerts": [str(a) for a in alerts],
                    "timestamp": time.time(),
                })
                tick += 1
            except Exception:
                pass
            time.sleep(interval)

    thread = threading.Thread(target=_broadcast_loop, daemon=True)
    thread.start()

    return app, socketio


def _serialise(data: dict) -> dict:
    """Convert data to a JSON-safe dict (handle None, special floats, etc.)."""
    import math
    import json

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return round(obj, 2)
        return obj

    return _clean(data)


def _serialise(data: dict) -> dict:
    import math
    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return round(obj, 2)
        return obj
    return _clean(data)
