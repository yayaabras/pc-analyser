"""Network collector — interfaces, rates, errors, retransmits, gateway latency."""

import subprocess
import shutil
import time
import psutil


def collect_network() -> list[dict]:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    io1 = psutil.net_io_counters(pernic=True)
    time.sleep(0.5)
    io2 = psutil.net_io_counters(pernic=True)
    dt = 0.5

    gateway_ip = _get_default_gateway()
    gateway_latency_ms = _ping_latency(gateway_ip) if gateway_ip else None

    interfaces = []
    for name, addr_list in addrs.items():
        iface_stats = stats.get(name)
        is_up = iface_stats.isup if iface_stats else False

        ipv4 = ipv6 = mac = None
        for addr in addr_list:
            fn = addr.family.name
            if fn == "AF_INET":
                ipv4 = addr.address
            elif fn == "AF_INET6":
                ipv6 = addr.address
            elif fn in ("AF_PACKET", "AF_LINK"):
                mac = addr.address

        c1 = io1.get(name)
        c2 = io2.get(name)

        send_kbps = recv_kbps = None
        errin = errout = dropin = dropout = None
        pkts_sent = pkts_recv = None

        if c1 and c2:
            send_kbps = round((c2.bytes_sent - c1.bytes_sent) / dt / 1024, 1)
            recv_kbps = round((c2.bytes_recv - c1.bytes_recv) / dt / 1024, 1)
            errin = c2.errin
            errout = c2.errout
            dropin = c2.dropin
            dropout = c2.dropout
            pkts_sent = c2.packets_sent
            pkts_recv = c2.packets_recv

        interfaces.append({
            "name": name,
            "is_up": is_up,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "mac": mac,
            "speed_mbps": iface_stats.speed if iface_stats else None,
            "send_rate_kbps": send_kbps,
            "recv_rate_kbps": recv_kbps,
            "bytes_sent_mb": round(c2.bytes_sent / 1024 ** 2, 2) if c2 else None,
            "bytes_recv_mb": round(c2.bytes_recv / 1024 ** 2, 2) if c2 else None,
            "packets_sent": pkts_sent,
            "packets_recv": pkts_recv,
            "errors_in": errin,
            "errors_out": errout,
            "drops_in": dropin,
            "drops_out": dropout,
            "gateway_ip": gateway_ip if ipv4 else None,
            "gateway_latency_ms": gateway_latency_ms if ipv4 else None,
        })

    return interfaces


def _get_default_gateway() -> str | None:
    """Read default gateway from /proc/net/route (Linux)."""
    try:
        with open("/proc/net/route") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3 and parts[1] == "00000000":
                    gw_hex = parts[2]
                    # Convert little-endian hex to IP
                    b = bytes.fromhex(gw_hex)
                    return ".".join(str(b) for b in reversed(b))
    except OSError:
        pass
    return None


def _ping_latency(host: str, count: int = 3) -> float | None:
    """Ping host and return average RTT in ms."""
    if not shutil.which("ping"):
        return None
    try:
        result = subprocess.run(
            ["ping", "-c", str(count), "-W", "1", host],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if "avg" in line or "rtt" in line:
                # Format: rtt min/avg/max/mdev = 0.123/0.456/0.789/0.100 ms
                parts = line.split("=")[-1].strip().split("/")
                if len(parts) >= 2:
                    return round(float(parts[1]), 2)
    except Exception:
        pass
    return None
