"""Network collector — interfaces, addresses, bytes sent/received, speeds."""

import time
import psutil


def collect_network() -> list[dict]:
    """Return a list of dicts, one per active network interface."""
    interfaces = []

    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    io1 = psutil.net_io_counters(pernic=True)
    time.sleep(0.5)
    io2 = psutil.net_io_counters(pernic=True)

    for iface_name, addr_list in addrs.items():
        iface_stats = stats.get(iface_name)
        is_up = iface_stats.isup if iface_stats else False

        ipv4 = None
        ipv6 = None
        mac = None

        for addr in addr_list:
            if addr.family.name == "AF_INET":
                ipv4 = addr.address
            elif addr.family.name == "AF_INET6":
                ipv6 = addr.address
            elif addr.family.name in ("AF_PACKET", "AF_LINK"):
                mac = addr.address

        # Calculate speed (bytes/sec over the 0.5s sample)
        send_rate = recv_rate = None
        c1 = io1.get(iface_name)
        c2 = io2.get(iface_name)
        if c1 and c2:
            dt = 0.5
            send_rate = round((c2.bytes_sent - c1.bytes_sent) / dt / 1024, 1)
            recv_rate = round((c2.bytes_recv - c1.bytes_recv) / dt / 1024, 1)

        interfaces.append({
            "name": iface_name,
            "is_up": is_up,
            "ipv4": ipv4,
            "ipv6": ipv6,
            "mac": mac,
            "speed_mbps": iface_stats.speed if iface_stats else None,
            "send_rate_kbps": send_rate,
            "recv_rate_kbps": recv_rate,
            "bytes_sent_mb": round(c2.bytes_sent / 1024 ** 2, 2) if c2 else None,
            "bytes_recv_mb": round(c2.bytes_recv / 1024 ** 2, 2) if c2 else None,
        })

    return interfaces


