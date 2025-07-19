import functools
import importlib.util
import json
import logging
from logging.handlers import RotatingFileHandler
from math import ceil
import os
import sys
import time

from svcutils.bootstrap import get_app_dir, get_work_dir   # keep in bootstrap, import from service
from svcutils.utils import (check_cpu_percent, get_file_mtime,
                            get_volume_labels, is_fullscreen,
                            is_online, pid_exists)


LOCK_FILENAME = '.svc.lock'

logger = logging.getLogger(__name__)


def setup_logging(logger, path, name, max_size=1024000):
    logging.basicConfig(level=logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(levelname)s [PID %(process)d] '
                                  '%(funcName)s(%(lineno)d) %(message)s')
    if sys.stdout and not sys.stdout.isatty():
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.setLevel(logging.DEBUG)
        logger.addHandler(stdout_handler)
    os.makedirs(path, exist_ok=True)
    file_handler = RotatingFileHandler(os.path.join(path, f'{name}.log'),
                                       mode='a', maxBytes=max_size, backupCount=0,
                                       encoding='utf-8', delay=0)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)


def get_logger(path, name):
    setup_logging(logger, path=path, name=name)
    return logger


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
                 requires_online=False, must_check_new_volume=False):
        self.file = os.path.join(work_dir, '.svc-tracker.json')
        self.min_uptime = min_uptime
        self.requires_online = requires_online
        self.must_check_new_volume = must_check_new_volume
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

    def _generate_update_item(self):
        return {
            'ts': time.time(),
            'is_online': is_online() if self.requires_online else None,
            'volume_labels': get_volume_labels() if self.must_check_new_volume else None,
        }

    def update(self, last_run_ts):
        begin_ts = max(0, last_run_ts - (self.check_delta or 0))
        self.data = [r for r in self.data if r['ts'] > begin_ts] + [self._generate_update_item()]
        with open(self.file, 'w') as fd:
            json.dump(self.data, fd)

    def check_new_volume(self, last_run_ts):
        if not self.must_check_new_volume:
            return False

        def get_labels(item):
            return set(item['volume_labels'] or [])

        try:
            before = [r for r in self.data if r['ts'] < last_run_ts][-1]
            after = [r for r in self.data if r['ts'] > last_run_ts][-1]
            return not get_labels(after).issubset(get_labels(before))
        except IndexError:
            return False

    def check_uptime(self):
        if not self.check_delta:
            return True
        now = time.time()
        tds = [int(d['ts'] - now) for d in self.data
               if d['ts'] > now - self.check_delta
               and (d['is_online'] or not self.requires_online)]
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
        last_run_ts = self.run_file.get_ts()
        next_run_delta = last_run_ts + self.run_delta - time.time()
        # if (not self.tracker.must_check_new_volume and self.tracker.check_delta
        #         and next_run_delta > self.tracker.check_delta):
        #     return False
        self.tracker.update(last_run_ts)
        if next_run_delta > 0 and not self.tracker.check_new_volume(last_run_ts):
            return False
        if not self.tracker.check_uptime():
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
