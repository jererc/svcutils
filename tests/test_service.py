from datetime import datetime, timedelta
import logging
from multiprocessing import Process
import os
from pprint import pprint
import shutil
import time
import unittest
from unittest.mock import patch

from tests import WORK_DIR
from svcutils import service as module


logger = logging.getLogger(__name__)


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


class LoggerTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.filename = 'test'
        self.log_file = os.path.join(WORK_DIR, f'{self.filename}.log')

    def test_1(self):
        logger.debug('debug')
        logger.info('info')
        logger.error('error')
        self.assertFalse(os.path.exists(self.log_file))

        module.setup_logging(WORK_DIR, self.filename)
        logger.debug('debug')
        logger.info('info')
        logger.error('error')
        with open(self.log_file) as fd:
            lines = fd.read().splitlines()
        pprint(lines)
        self.assertEqual(len(lines), 2)
        self.assertTrue(' INFO ' in lines[0])
        self.assertTrue(' ERROR ' in lines[1])


class ConfigTestCase(unittest.TestCase):
    def test_1(self):
        self.assertRaises(Exception, module.Config, 'invalid')

        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        config_file = os.path.join(WORK_DIR, 'config.py')
        with open(config_file, 'w') as fd:
            fd.write("""invalid""")
        self.assertRaises(Exception, module.Config, config_file)

        with open(config_file, 'w') as fd:
            fd.write("""CONST1 = 'value1'""")
        config = module.Config(config_file)
        self.assertEqual(config.CONST1, 'value1')
        self.assertEqual(config.CONST2, None)
        config = module.Config(config_file, CONST2='default2')
        self.assertEqual(config.CONST1, 'value1')
        self.assertEqual(config.CONST2, 'default2')
        self.assertEqual(config.CONST3, None)


class DisplayEnvTestCase(unittest.TestCase):
    def test_display_env(self):
        res = module.get_display_env()
        pprint(res)
        self.assertTrue({res[k] for k in ['DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS']})


class TargetTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.work_dir = WORK_DIR

    def test_target(self):
        self.wrapper_run = False
        self.target_run = False
        self.result = None

        def wrapper(*args, **kwargs):
            print(f'{args=} {kwargs=}')
            self.wrapper_run = True

            def target(p1, p2):
                self.target_run = True
                return p1, p2

            self.result = target(*args, **kwargs)
            return self.result

        se = module.Service(
            target=wrapper,
            args=('123',),
            kwargs={'p2': '456'},
            work_dir=self.work_dir,
        )
        with patch.object(se, '_must_run', return_value=False):
            se.run_once()
        self.assertFalse(self.wrapper_run)
        self.assertFalse(self.target_run)
        self.assertEqual(self.result, None)

        with patch.object(se, '_must_run', return_value=True):
            se.run_once()
        self.assertTrue(self.wrapper_run)
        self.assertTrue(self.target_run)
        self.assertEqual(self.result, ('123', '456'))


class SingleInstanceTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.lock_file = os.path.join(WORK_DIR, module.LOCK_FILENAME)
        self.pid_file = os.path.join(WORK_DIR, 'pids.txt')

    @module.single_instance(WORK_DIR)
    def _target(self):
        with open(self.pid_file, 'a') as fd:
            fd.write(f'{os.getpid()}\n')
        time.sleep(2)

    def test_1(self):
        pids = []
        p1 = Process(target=self._target)
        p1.start()
        pids.append(p1.pid)
        p2 = Process(target=self._target)
        p2.start()
        time.sleep(3)
        p3 = Process(target=self._target)
        p3.start()
        pids.append(p3.pid)
        time.sleep(3)
        self.assertFalse(os.path.exists(self.lock_file))
        with open(self.pid_file) as fd:
            ran_pids = [int(r) for r in fd.read().splitlines()]
        self.assertEqual(ran_pids, pids)


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.runs = 0
        self.now = datetime.now().replace(minute=0, second=0)

    def _target(self):
        self.runs += 1

    def _run_once(self, now, service_args=None, volume_labels=None, is_fullscreen=False):
        print('*' * 80)
        print(f'running at {now=}')
        service = module.Service(target=self._target, work_dir=WORK_DIR, run_delta=60 * 30, **(service_args or {}))
        with patch('svcutils.service.datetime') as mock_datetime, \
                patch('svcutils.service.time.time', return_value=now.timestamp()), \
                patch('svcutils.service.is_fullscreen', return_value=is_fullscreen), \
                patch('svcutils.service.get_volume_labels', return_value=volume_labels):
            mock_datetime.now.return_value = now
            service.run_once()
        data = service._load_tracker_data()
        pprint(data)
        return data

    def _check_data(self, data, last_run_dt, last_attempt_dt, last_attempt_run=True):
        if last_run_dt:
            self.assertEqual(data['last_run']['ts'], last_run_dt.timestamp())
        else:
            self.assertEqual(data['last_run'], None)
        self.assertEqual(data['attempts'][-1]['ts'], last_attempt_dt.timestamp())
        self.assertEqual(data['attempts'][-1]['run'], last_attempt_run)
        self.assertEqual(data['attempts'][-1]['dt'], last_attempt_dt.isoformat())

    def test_init(self):
        service = module.Service(target=self._target, work_dir=WORK_DIR, run_delta=60 * 30)
        data = service._load_tracker_data()
        self.assertEqual(data, {'attempts': [], 'last_run': None})

    def test_default(self):
        dt1 = self.now
        data = self._run_once(dt1)
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt1, last_attempt_run=True)

        dt2 = self.now + timedelta(minutes=2)
        data = self._run_once(dt2)
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt2, last_attempt_run=False)

        dt3 = self.now + timedelta(minutes=120)
        data = self._run_once(dt3)
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt3, last_attempt_run=True)

        dt4 = self.now + timedelta(minutes=122)
        data = self._run_once(dt4)
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt4, last_attempt_run=False)

        dt5 = self.now + timedelta(minutes=240)
        data = self._run_once(dt5)
        self._check_data(data, last_run_dt=dt5, last_attempt_dt=dt5, last_attempt_run=True)

        self.assertEqual(self.runs, 3)

    def test_no_volume_change(self):
        service_args = {'trigger_on_volume_change': True}

        dt1 = self.now
        data = self._run_once(dt1, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt1, last_attempt_run=True)

        dt2 = self.now + timedelta(minutes=2)
        data = self._run_once(dt2, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt2, last_attempt_run=False)

        dt3 = self.now + timedelta(minutes=4)
        data = self._run_once(dt3, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt3, last_attempt_run=False)

    def test_new_volume(self):
        service_args = {'trigger_on_volume_change': True}

        dt1 = self.now
        data = self._run_once(dt1, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt1, last_attempt_run=True)

        dt2 = self.now + timedelta(minutes=2)
        data = self._run_once(dt2, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt2, last_attempt_run=False)

        dt3 = self.now + timedelta(minutes=4)
        data = self._run_once(dt3, service_args, volume_labels=['vol1', 'vol2'])
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt3, last_attempt_run=True)

    def test_new_volume_multiple_attempts(self):
        service_args = {'trigger_on_volume_change': True}

        dt1 = self.now
        data = self._run_once(dt1, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt1, last_attempt_run=True)

        dt2 = self.now + timedelta(minutes=2)
        data = self._run_once(dt2, service_args, volume_labels=['vol1', 'vol2'], is_fullscreen=True)
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt2, last_attempt_run=False)

        dt3 = self.now + timedelta(minutes=4)
        data = self._run_once(dt3, service_args, volume_labels=['vol1', 'vol2'])
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt3, last_attempt_run=True)

        dt4 = self.now + timedelta(minutes=6)
        data = self._run_once(dt4, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt4, last_attempt_run=False)

    def test_new_volume_retry(self):
        service_args = {'trigger_on_volume_change': True}

        dt1 = self.now
        data = self._run_once(dt1, service_args, volume_labels=['vol1', 'vol2'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt1, last_attempt_run=True)

        dt2 = self.now + timedelta(minutes=2)
        data = self._run_once(dt2, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt1, last_attempt_dt=dt2, last_attempt_run=False)

        dt3 = self.now + timedelta(minutes=4)
        data = self._run_once(dt3, service_args, volume_labels=['vol1', 'vol2'])
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt3, last_attempt_run=True)

        dt4 = self.now + timedelta(minutes=6)
        data = self._run_once(dt4, service_args, volume_labels=['vol1'])
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt4, last_attempt_run=False)

    def test_min_uptime(self):
        service_args = {'min_uptime': 180}

        dt1 = self.now
        data = self._run_once(dt1, service_args)
        self._check_data(data, last_run_dt=None, last_attempt_dt=dt1, last_attempt_run=False)

        dt2 = self.now + timedelta(minutes=2)
        data = self._run_once(dt2, service_args)
        self._check_data(data, last_run_dt=None, last_attempt_dt=dt2, last_attempt_run=False)

        dt3 = self.now + timedelta(minutes=4)
        data = self._run_once(dt3, service_args)
        self._check_data(data, last_run_dt=dt3, last_attempt_dt=dt3, last_attempt_run=True)
