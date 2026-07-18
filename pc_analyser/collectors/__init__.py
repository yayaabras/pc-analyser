"""Hardware data collectors."""

from .cpu import collect_cpu
from .memory import collect_memory
from .gpu import collect_gpu
from .thermal import collect_thermal
from .storage import collect_storage
from .network import collect_network
from .battery import collect_battery
from .motherboard import collect_motherboard

__all__ = [
    "collect_cpu",
    "collect_memory",
    "collect_gpu",
    "collect_thermal",
    "collect_storage",
    "collect_network",
    "collect_battery",
    "collect_motherboard",
]


def collect_all() -> dict:
    """Collect all hardware metrics in one call."""
    return {
        "cpu": collect_cpu(),
        "memory": collect_memory(),
        "gpu": collect_gpu(),
        "thermal": collect_thermal(),
        "storage": collect_storage(),
        "network": collect_network(),
        "battery": collect_battery(),
        "motherboard": collect_motherboard(),
    }
