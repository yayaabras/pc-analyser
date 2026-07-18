"""Motherboard and BIOS collector — model, manufacturer, BIOS version."""

import platform
import os


def collect_motherboard() -> dict:
    """Return motherboard and BIOS information."""
    result = {
        "manufacturer": None,
        "product": None,
        "version": None,
        "serial": None,
        "bios_vendor": None,
        "bios_version": None,
        "bios_date": None,
    }

    if platform.system() == "Windows":
        result.update(_collect_windows())
    elif platform.system() == "Linux":
        result.update(_collect_linux())

    return result


def _collect_windows() -> dict:
    """Use WMI on Windows to get motherboard and BIOS info."""
    try:
        import wmi  # type: ignore
        c = wmi.WMI()
        data = {}

        for board in c.Win32_BaseBoard():
            data["manufacturer"] = (board.Manufacturer or "").strip() or None
            data["product"] = (board.Product or "").strip() or None
            data["version"] = (board.Version or "").strip() or None
            data["serial"] = (board.SerialNumber or "").strip() or None
            break

        for bios in c.Win32_BIOS():
            data["bios_vendor"] = (bios.Manufacturer or "").strip() or None
            data["bios_version"] = (bios.SMBIOSBIOSVersion or "").strip() or None
            data["bios_date"] = (bios.ReleaseDate or "")[:8] or None
            break

        return data
    except Exception:
        return {}


def _collect_linux() -> dict:
    """Read DMI info from /sys/class/dmi/id/ on Linux."""
    dmi_base = "/sys/class/dmi/id"
    if not os.path.exists(dmi_base):
        return {}

    def _read(filename: str) -> str | None:
        try:
            path = os.path.join(dmi_base, filename)
            with open(path) as f:
                val = f.read().strip()
                return val if val else None
        except OSError:
            return None

    return {
        "manufacturer": _read("board_vendor"),
        "product": _read("board_name"),
        "version": _read("board_version"),
        "serial": _read("board_serial"),
        "bios_vendor": _read("bios_vendor"),
        "bios_version": _read("bios_version"),
        "bios_date": _read("bios_date"),
    }
