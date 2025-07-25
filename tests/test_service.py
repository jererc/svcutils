import logging
from multiprocessing import Process
import os
from pprint import pprint
import shutil
import signal
import time
import unittest
from unittest.mock import patch

import psutil

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


class ServiceTrackerTestCase(unittest.TestCase):
    def setUp(self):
        self.target = int
        self.work_dir = WORK_DIR
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)

    def test_params(self):
        st = module.ServiceTracker(self.work_dir)
        self.assertEqual(st.check_delta, None)

        st = module.ServiceTracker(self.work_dir, min_uptime=0)
        self.assertEqual(st.check_delta, None)

        st = module.ServiceTracker(self.work_dir, min_uptime=1)
        self.assertEqual(st.uptime_precision, 180)
        self.assertEqual(st.check_delta, 181)

        st = module.ServiceTracker(self.work_dir,
                                   min_uptime=60,
                                   update_delta=10)
        self.assertEqual(st.uptime_precision, 15)
        self.assertEqual(st.check_delta, 75)

    def test_service_params(self):
        se = module.Service(
            target=self.target,
            work_dir=self.work_dir,
            run_delta=10,
        )
        self.assertEqual(se.tracker.min_uptime, None)
        self.assertEqual(se.tracker.uptime_precision, 180)
        self.assertFalse(se.tracker.requires_online)

        se = module.Service(
            target=self.target,
            work_dir=self.work_dir,
            run_delta=10,
            min_uptime=300,
            update_delta=120,
            requires_online=True,
        )
        self.assertEqual(se.tracker.min_uptime, 300)
        self.assertEqual(se.tracker.uptime_precision, 180)
        self.assertTrue(se.tracker.requires_online)

    def test_data(self):
        st = module.ServiceTracker(self.work_dir, min_uptime=1,
                                   requires_online=True, must_check_new_volume=10)
        st.update(0)
        pprint(st.data)
        self.assertTrue(st.data)
        data = st.data[-1]
        self.assertIsInstance(data, dict)
        self.assertIsInstance(data['ts'], float)
        self.assertIsInstance(data['is_online'], bool)
        self.assertIsInstance(data['volume_labels'], list)

    def test_check_new_volume(self):
        def item(volume_labels, ts):
            return {'ts': ts, 'volume_labels': volume_labels}

        last_run_ts = time.time() - 60

        st = module.ServiceTracker(self.work_dir, min_uptime=1, must_check_new_volume=False)
        st.data = [item(['a'], last_run_ts - 1), item(['a', 'b'], last_run_ts + 1)]
        self.assertFalse(st.check_new_volume(last_run_ts))

        st = module.ServiceTracker(self.work_dir, min_uptime=1, must_check_new_volume=True)
        st.data = []
        self.assertFalse(st.check_new_volume(last_run_ts))
        st.data = [item(['a'], last_run_ts - 1)]
        self.assertFalse(st.check_new_volume(last_run_ts))
        st.data = [item(['a'], last_run_ts + 1)]
        self.assertFalse(st.check_new_volume(last_run_ts))
        st.data = [item([], last_run_ts - 1), item([], last_run_ts + 1)]
        self.assertFalse(st.check_new_volume(last_run_ts))
        st.data = [item(['a', 'b'], last_run_ts - 1), item(['a'], last_run_ts + 1), item(['a', 'b'], last_run_ts + 2)]
        self.assertFalse(st.check_new_volume(last_run_ts))
        st.data = [item(['a', 'b'], last_run_ts - 1), item(['a'], last_run_ts + 1)]
        self.assertFalse(st.check_new_volume(last_run_ts))

        st.data = [item(['a'], last_run_ts - 1), item(['a', 'b'], last_run_ts + 1)]
        self.assertTrue(st.check_new_volume(last_run_ts))
        st.data = [item(['a', 'b'], last_run_ts - 1), item(['b', 'c'], last_run_ts + 1)]
        self.assertTrue(st.check_new_volume(last_run_ts))
        st.data = [item(['a'], last_run_ts - 1), item(['a', 'b'], last_run_ts + 1), item(['a', 'b'], last_run_ts + 2)]
        self.assertTrue(st.check_new_volume(last_run_ts))
        st.data = [item(['a'], last_run_ts - 1), item(['a', 'b'], last_run_ts + 1), item(['a'], last_run_ts + 1)]
        self.assertFalse(st.check_new_volume(last_run_ts))
        st.data = [item(['a', 'b'], last_run_ts - 1), item(['a'], last_run_ts + 1)]
        self.assertFalse(st.check_new_volume(last_run_ts))

    def test_low_uptime(self):
        st = module.ServiceTracker(self.work_dir,
                                   min_uptime=60,
                                   requires_online=False,
                                   update_delta=120)

        now = time.time()
        st.data = [
            {'ts': now - 241, 'is_online': True},
            {'ts': now, 'is_online': True},
        ]
        self.assertFalse(st.check_uptime())

        now = time.time()
        st.data = [
            {'ts': now - 121, 'is_online': True},
            {'ts': now, 'is_online': True},
        ]
        self.assertTrue(st.check_uptime())

    def test_check_uptime(self):
        st = module.ServiceTracker(self.work_dir,
                                   min_uptime=300,
                                   requires_online=False,
                                   update_delta=120)

        now = time.time()
        st.data = [
            {'ts': now - 241, 'is_online': True},
            {'ts': now - 121, 'is_online': True},
            {'ts': now, 'is_online': True},
        ]
        self.assertFalse(st.check_uptime())

        now = time.time()
        st.data = [
            {'ts': now - 361, 'is_online': True},
            {'ts': now - 61, 'is_online': True},
            {'ts': now, 'is_online': True},
        ]
        self.assertFalse(st.check_uptime())

        now = time.time()
        st.data = [
            {'ts': now - 361, 'is_online': True},
            {'ts': now - 241, 'is_online': True},
            {'ts': now - 121, 'is_online': True},
            {'ts': now, 'is_online': True},
        ]
        self.assertTrue(st.check_uptime())


class DisplayEnvTestCase(unittest.TestCase):
    def test_display_env(self):
        res = module.get_display_env()
        pprint(res)
        self.assertTrue({res[k] for k in ['DISPLAY', 'XAUTHORITY', 'DBUS_SESSION_BUS_ADDRESS']})


class MustRunTestCase(unittest.TestCase):
    def setUp(self):
        self.target = int
        self.work_dir = WORK_DIR

    def test_run(self):
        with patch.object(module.RunFile, 'get_ts',
                          return_value=time.time() - 1):
            self.assertFalse(module.Service(
                target=self.target,
                work_dir=self.work_dir,
                run_delta=10,
            )._must_run())

        with patch.object(module.RunFile, 'get_ts',
                          return_value=time.time() - 11):
            self.assertTrue(module.Service(
                target=self.target,
                work_dir=self.work_dir,
                run_delta=10,
            )._must_run())

    def test_cpu_percent(self):
        with patch.object(module, 'is_fullscreen', return_value=False):

            with patch.object(module.RunFile, 'get_ts',
                              return_value=time.time() - 11), \
                    patch.object(psutil, 'cpu_percent',
                                 return_value=20):
                self.assertFalse(module.Service(
                    target=self.target,
                    work_dir=self.work_dir,
                    run_delta=10,
                    max_cpu_percent=10,
                )._must_run())

            with patch.object(module.RunFile, 'get_ts',
                              return_value=time.time() - 11), \
                    patch.object(psutil, 'cpu_percent',
                                 return_value=1):
                self.assertTrue(module.Service(
                    target=self.target,
                    work_dir=self.work_dir,
                    run_delta=10,
                    max_cpu_percent=10,
                )._must_run())


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


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)

    def test_run_once(self):
        self.attempts = 0
        self.runs = 0

        def target():
            self.runs += 1

        svc = module.Service(
            target=target,
            work_dir=WORK_DIR,
            run_delta=1,
        )
        end_ts = time.time() + 3
        while time.time() < end_ts:
            svc.run_once()
            self.attempts += 1
            time.sleep(.2)
        print(f'{self.attempts=}, {self.runs=}')
        self.assertTrue(self.attempts >= 10)
        self.assertTrue(self.runs <= 4)

    def test_run_exc(self):
        self.result_path = os.path.join(WORK_DIR, '_test_result')

        def target():
            with open(self.result_path, 'a') as fd:
                fd.write('call\n')
            raise Exception('failed')

        def run():
            module.Service(
                target=target,
                work_dir=WORK_DIR,
                run_delta=1,
                daemon_loop_delta=.2,
            ).run()

        proc = Process(target=run)
        proc.start()
        time.sleep(3)
        os.kill(proc.pid, signal.SIGTERM)

        with open(self.result_path) as fd:
            lines = fd.read().splitlines()
        print(lines)
        self.assertEqual(lines, ['call'] * 3)

    def test_run(self):
        self.result_path = os.path.join(WORK_DIR, '_test_result')

        def target():
            with open(self.result_path, 'a') as fd:
                fd.write('call\n')

        def run():
            module.Service(
                target=target,
                work_dir=WORK_DIR,
                run_delta=1,
                daemon_loop_delta=.2,
            ).run()

        proc = Process(target=run)
        proc.start()
        time.sleep(3)
        os.kill(proc.pid, signal.SIGTERM)

        with open(self.result_path) as fd:
            lines = fd.read().splitlines()
        print(lines)
        self.assertEqual(lines, ['call'] * 3)


class RuntimeTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)

    def test_offline(self):
        self.runs = 0

        def target():
            self.runs += 1

        svc = module.Service(
            target=target,
            work_dir=WORK_DIR,
            run_delta=1,
            min_uptime=5,
            requires_online=True,
        )
        with patch.object(module, 'is_online', return_value=False):
            end_ts = time.time() + 7
            while time.time() < end_ts:
                svc.run_once()
                time.sleep(1)
        self.assertFalse(self.runs)

    def test_online(self):
        self.runs = 0

        def target():
            self.runs += 1

        svc = module.Service(
            target=target,
            work_dir=WORK_DIR,
            run_delta=1,
            min_uptime=5,
            requires_online=True,
        )
        end_ts = time.time() + 7
        while time.time() < end_ts:
            svc.run_once()
            time.sleep(1)
        self.assertTrue(self.runs)


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
