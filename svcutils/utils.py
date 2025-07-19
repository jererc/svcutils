import ctypes
import json
import logging
import os
import socket
import subprocess
import sys

import psutil


logger = logging.getLogger(__name__)


def get_file_mtime(x):
    return os.stat(x).st_mtime


def pid_exists(pid):
    return psutil.pid_exists(pid)


def get_display_env(keys=None):
    if keys is None:
        keys = ['DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS']
    for proc in psutil.process_iter(['pid', 'environ']):
        try:
            env = proc.info['environ'] or {}
            res = {k: env.get(k) for k in keys}
            if all(res.values()):
                return res
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Fallback to default display
    res = {
        'DISPLAY': ':0',
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{os.getuid()}/bus',
    }
    xauth_paths = [
        os.path.expanduser('~/.Xauthority'),
        f'/run/user/{os.getuid()}/gdm/Xauthority',
        '/var/run/gdm/auth-for-gdm*/database'
    ]
    for path in xauth_paths:
        if os.path.exists(path):
            res['XAUTHORITY'] = path
            break
    return res


def _is_fullscreen_windows(tolerance=2):
    import win32api
    import win32con
    import win32gui
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd or not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
        return False
    win_left, win_top, win_right, win_bottom = win32gui.GetWindowRect(hwnd)
    hmon = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
    mon_info = win32api.GetMonitorInfo(hmon)
    mon_left, mon_top, mon_right, mon_bottom = mon_info["Monitor"]
    res = (
        abs(win_left - mon_left) <= tolerance and
        abs(win_top - mon_top) <= tolerance and
        abs(win_right - mon_right) <= tolerance and
        abs(win_bottom - mon_bottom) <= tolerance
    )
    if res:
        logger.info(f'window "{win32gui.GetWindowText(hwnd)}" is fullscreen')
    return res


def _is_fullscreen_linux():
    from ewmh import EWMH
    if not os.environ.get('DISPLAY'):
        os.environ.update(get_display_env())
    ewmh = EWMH()
    win = ewmh.getActiveWindow()
    if win is None:
        return False
    states = ewmh.getWmState(win, str) or []
    res = "_NET_WM_STATE_FULLSCREEN" in states
    if res:
        title = ewmh.getWmName(win).decode('utf-8')   # or win.get_wm_name()
        logger.info(f'window "{title}" is fullscreen')
    return res


def is_fullscreen():
    try:
        return {'win32': _is_fullscreen_windows,
                'linux': _is_fullscreen_linux}[sys.platform]()
    except Exception:
        logger.exception('failed to check fullscreen')
        return False


def is_online(host='8.8.8.8', port=53, timeout=3):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except OSError:
        return False


def check_cpu_percent(max_percent, interval=1):
    if max_percent and psutil.cpu_percent(interval=interval) > max_percent:
        logger.info(f'cpu usage is greater than {max_percent}%')
        return False
    return True


def _list_windows_mountpoint_labels():
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

    def get_label(mountpoint):
        label_buf = ctypes.create_unicode_buffer(261)
        fs_buf = ctypes.create_unicode_buffer(261)
        ok = kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(mountpoint),   # lpRootPathName
            label_buf,   # lpVolumeNameBuffer
            len(label_buf),   # nVolumeNameSize (chars)
            None, None, None,   # serial, comp.len, flags – unused
            fs_buf,   # lpFileSystemNameBuffer
            len(fs_buf)   # nFileSystemNameSize (chars)
        )
        return label_buf.value if ok else None

    return {d.mountpoint: get_label(d.mountpoint)
            for d in psutil.disk_partitions(all=True)}


def _list_linux_mountpoint_labels():
    lsblk = subprocess.run(
        ["lsblk", "-o", "LABEL,MOUNTPOINT", "--json", "--paths"],
        capture_output=True, text=True, check=True
    )
    data = json.loads(lsblk.stdout)
    mp_labels = {item["mountpoint"]: item["label"]
                 for item in data.get("blockdevices", [])
                 if item.get("mountpoint") is not None}
    return {d.mountpoint: mp_labels.get(d.mountpoint)
            for d in psutil.disk_partitions(all=False)}


def list_mountpoint_labels():
    try:
        return {'win32': _list_windows_mountpoint_labels,
                'linux': _list_linux_mountpoint_labels}[sys.platform]()
    except Exception:
        logger.exception('failed to list mountpoint labels')
        return {}


def get_volume_labels():
    return [r for r in list_mountpoint_labels().values() if r]
