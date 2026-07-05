"""
tools/system_tools.py — System status: CPU, RAM, disk, battery, uptime.
Uses psutil for cross-platform system metrics.
"""

from __future__ import annotations

import datetime

from tools.base import ToolResult


def _get_psutil():
    import psutil
    return psutil


def system_status() -> dict:
    ps = _get_psutil()

    cpu = ps.cpu_percent(interval=0.1)

    mem = ps.virtual_memory()
    ram = {
        "total_gb": round(mem.total / (1024 ** 3), 2),
        "used_gb": round(mem.used / (1024 ** 3), 2),
        "percent": mem.percent,
    }

    disks = []
    for part in ps.disk_partitions():
        try:
            usage = ps.disk_usage(part.mountpoint)
            disks.append({
                "mount": part.mountpoint,
                "total_gb": round(usage.total / (1024 ** 3), 2),
                "used_gb": round(usage.used / (1024 ** 3), 2),
                "free_gb": round(usage.free / (1024 ** 3), 2),
                "percent": usage.percent,
                "fstype": part.fstype,
            })
        except PermissionError:
            continue

    battery: dict | None = None
    try:
        bat = ps.sensors_battery()
        if bat is not None:
            battery = {
                "percent": bat.percent,
                "plugged_in": bat.power_plugged or False,
                "minutes_left": round(bat.secsleft / 60) if bat.secsleft != -1 else None,
            }
    except Exception:
        pass

    boot_time = datetime.datetime.fromtimestamp(ps.boot_time())
    uptime = datetime.datetime.now() - boot_time

    return {
        "cpu_percent": cpu,
        "ram": ram,
        "disks": disks,
        "battery": battery,
        "uptime_hours": round(uptime.total_seconds() / 3600, 1),
        "boot_time": boot_time.isoformat(),
    }


def format_status(status: dict) -> str:
    lines = []
    lines.append(f"CPU: {status['cpu_percent']}%")
    r = status['ram']
    lines.append(f"RAM: {r['percent']}% ({r['used_gb']}/{r['total_gb']} GB)")
    for d in status['disks']:
        lines.append(f"Disk {d['mount']}: {d['percent']}% ({d['used_gb']}/{d['total_gb']} GB free)")
    bat = status.get('battery')
    if bat:
        plug = "Plugged in" if bat['plugged_in'] else "On battery"
        mins = f", {bat['minutes_left']}m left" if bat['minutes_left'] else ""
        lines.append(f"Battery: {bat['percent']}% ({plug}{mins})")
    lines.append(f"Uptime: {status['uptime_hours']}h")
    return "\n".join(lines)


def battery_status(params: dict) -> ToolResult:
    ps = _get_psutil()
    try:
        bat = ps.sensors_battery()
        if bat is None:
            return ToolResult(False, "No battery detected")
        plugged = bat.power_plugged or False
        mins = round(bat.secsleft / 60) if bat.secsleft != -1 else None
        status_parts = [f"{bat.percent}%"]
        status_parts.append("Plugged in" if plugged else "On battery")
        if mins:
            status_parts.append(f"{mins}m remaining")
        return ToolResult(
            True,
            " | ".join(status_parts),
            {"percent": bat.percent, "plugged_in": plugged, "minutes_left": mins},
        )
    except Exception as exc:
        return ToolResult(False, f"Battery check failed: {exc}")


def system_processes(params: dict) -> ToolResult:
    ps = _get_psutil()
    sort_by = str(params.get("sort_by", "cpu")).lower()
    limit = min(int(params.get("limit", 10)), 50)

    processes = []
    for proc in ps.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            processes.append(proc.info)
        except (ps.NoSuchProcess, ps.AccessDenied):
            continue

    key = "memory_percent" if sort_by == "memory" else "cpu_percent"

    processes.sort(key=lambda p: p.get(key, 0) or 0, reverse=True)
    top = processes[:limit]

    lines = [f"{'PID':<6} {'CPU%':<6} {'MEM%':<6}  Name"]
    lines.append("-" * 40)
    for p in top:
        lines.append(f"{p['pid']:<6} {p.get('cpu_percent', 0) or 0:<6.1f} {p.get('memory_percent', 0) or 0:<6.1f}  {p['name']}")

    return ToolResult(
        True,
        f"Top {len(top)} processes by {sort_by}:\n" + "\n".join(lines),
        {"processes": top, "sort_by": sort_by},
    )


# ── Volume ducking helpers ─────────────────────────────────────────────────


def _get_pycaw_volume():
    """Lazy-import and return the pycaw volume interface."""
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def get_system_volume() -> float | None:
    try:
        return _get_pycaw_volume().GetMasterVolumeLevelScalar()
    except Exception:
        return None


def set_system_volume(level: float):
    try:
        _get_pycaw_volume().SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)
    except Exception:
        pass
