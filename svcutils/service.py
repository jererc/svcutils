import functools
import importlib.util
import json
import logging
from logging.handlers import RotatingFileHandler
from math import ceil
import os
import socket
import sys
import time

from svcutils.bootstrap import get_app_dir, get_work_dir


LOCK_FILENAME = '.svc.lock'

logger = logging.getLogger(__name__)


def setup_logging(logger, path, name, max_size=1024000):
    logging.basicConfig(level=logging.DEBUG)
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(funcName)s(%(lineno)d) %(message)s')
    if sys.stdout and not sys.stdout.isatty():
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)
    os.makedirs(path, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(path, f'{name}.log'),
        mode='a', maxBytes=max_size, backupCount=0,
        encoding='utf-8', delay=0)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)


def get_logger(path, name):
    setup_logging(logger, path=path, name=name)
    return logger


def is_online(host='8.8.8.8', port=53, timeout=3):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
        return True
    except OSError:
        return False


def get_file_mtime(x):
    return os.stat(x).st_mtime


def pid_exists(pid):
    import psutil
    return psutil.pid_exists(pid)


def single_instance(path):
    lockfile = os.path.join(path, LOCK_FILENAME)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if os.path.exists(lockfile):
                with open(lockfile, 'r') as fd:
                    try:
                        old_pid = int(fd.read().strip())
                    except ValueError:
                        old_pid = None
                if old_pid and pid_exists(old_pid):
                    raise SystemExit(f'Another instance (PID={old_pid}) is running. Exiting.')
                else:
                    logger.warning('Found a stale lockfile. Removing it.')
                    os.remove(lockfile)
            current_pid = os.getpid()
            with open(lockfile, 'w') as fd:
                fd.write(str(current_pid))
            try:
                return func(*args, **kwargs)
            finally:
                if os.path.exists(lockfile):
                    os.remove(lockfile)
        return wrapper
    return decorator


def get_display_env(keys=None):
    import psutil
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


def check_cpu_percent(max_percent, interval=1):
    if max_percent:
        import psutil
        if psutil.cpu_percent(interval=interval) > max_percent:
            logger.info(f'cpu usage is greater than {max_percent}%')
            return False
    return True


class ConfigNotFound(Exception):
    pass


class Config:
    def __init__(self, file, **defaults):
        self.file = os.path.realpath(os.path.expanduser(file))
        self.config = self._load()
        self.defaults = defaults

    def _load(self):
        if not os.path.exists(self.file):
            raise ConfigNotFound(self.file)
        spec = importlib.util.spec_from_file_location('config', self.file)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)
        return config

    def __getattr__(self, name, default=None):
        return getattr(self.config, name, self.defaults.get(name, default))


class RunFile:
    def __init__(self, file):
        self.file = file

    def get_ts(self, default=0):
        if not os.path.exists(self.file):
            return default
        return get_file_mtime(self.file)

    def touch(self):
        with open(self.file, 'w'):
            pass


class ServiceTracker:
    def __init__(self, work_dir, min_uptime=None, update_delta=120,
                 requires_online=False):
        self.file = os.path.join(work_dir, '.svc-tracker.json')
        self.min_uptime = min_uptime
        self.requires_online = requires_online
        self.uptime_precision = int(ceil(update_delta * 1.5))
        self.check_delta = self._get_check_delta()
        self.data = self._load()

    def _get_check_delta(self):
        return (self.min_uptime + self.uptime_precision
                if self.min_uptime else None)

    def _load(self):
        if not os.path.exists(self.file):
            return []
        with open(self.file) as fd:
            return json.load(fd)

    def update(self):
        if not self.check_delta:
            return
        now = time.time()
        self.data = ([r for r in self.data if r[0] > now - self.check_delta] +
                     [(int(now), int(is_online()) if self.requires_online else -1)])
        with open(self.file, 'w') as fd:
            json.dump(self.data, fd)

    def check(self):
        if not self.check_delta:
            return True
        now = time.time()
        tds = [int(t - now) for t, o in self.data
               if t > now - self.check_delta and (o or not self.requires_online)]
        values = {int((r + self.check_delta) // self.uptime_precision)
                  for r in tds}
        expected = set(range(0, int(ceil(self.check_delta
                                         / self.uptime_precision))))
        res = values >= expected
        if not res:
            logger.info(f'{"online " if self.requires_online else ""}'
                        f'uptime is less than {self.min_uptime} seconds')
        return res


class Service:
    def __init__(self, target, work_dir, args=None, kwargs=None,
                 run_delta=60, daemon_loop_delta=60, max_cpu_percent=None,
                 **tracker_args):
        self.target = target
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.work_dir = work_dir
        self.run_delta = run_delta
        self.daemon_loop_delta = daemon_loop_delta
        self.max_cpu_percent = max_cpu_percent
        self.tracker = ServiceTracker(work_dir, **tracker_args)
        self.run_file = RunFile(os.path.join(work_dir, '.svc.run'))

    def _must_run(self):
        run_delta = self.run_file.get_ts() + self.run_delta - time.time()
        if self.tracker.check_delta and run_delta > self.tracker.check_delta:
            return False
        self.tracker.update()
        if run_delta > 0:
            return False
        if not self.tracker.check():
            return False
        if is_fullscreen():
            return False
        if not check_cpu_percent(self.max_cpu_percent):
            return False
        return True

    def _attempt_run(self, force=False):
        try:
            if force or self._must_run():
                try:
                    self.target(*self.args, **self.kwargs)
                finally:
                    self.run_file.touch()
        except Exception:
            logger.exception('service failed')

    def run_once(self, force=False):
        @single_instance(self.work_dir)
        def run():
            self._attempt_run(force)

        run()

    def run(self):
        @single_instance(self.work_dir)
        def run():
            while True:
                self._attempt_run()
                logger.debug(f'sleeping for {self.daemon_loop_delta} seconds')
                time.sleep(self.daemon_loop_delta)

        run()
