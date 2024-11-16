import logging
from multiprocessing import Process
import os
import shutil
import signal
import time
import unittest
from unittest.mock import patch

import psutil

from svcutils import service as module


TEST_DIR = '_test_svcutils'
WORK_PATH = os.path.join(os.path.expanduser('~'), TEST_DIR)

module.logger.setLevel(logging.DEBUG)


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def makedirs(x):
    if not os.path.exists(x):
        os.makedirs(x)


class ServiceTrackerTestCase(unittest.TestCase):
    def setUp(self):
        self.target = int
        self.work_path = WORK_PATH

    def test_params(self):
        st = module.ServiceTracker(self.work_path, min_runtime=1)
        self.assertEqual(st.runtime_precision, 0)
        self.assertEqual(st.check_delta, 1)

        st = module.ServiceTracker(self.work_path, min_runtime=0)
        self.assertEqual(st.runtime_precision, 0)
        self.assertEqual(st.check_delta, 0)

        st = module.ServiceTracker(self.work_path, min_runtime=30)
        self.assertEqual(st.runtime_precision, 15)
        self.assertEqual(st.check_delta, 45)

        st = module.ServiceTracker(self.work_path, min_runtime=60,
            runtime_precision=10)
        self.assertEqual(st.runtime_precision, 10)
        self.assertEqual(st.check_delta, 70)

    def test_update(self):
        st = module.ServiceTracker(self.work_path, min_runtime=1)
        end_ts = time.time() + st.check_delta * 2
        while time.time() < end_ts:
            time.sleep(.1)
            st.update()
        self.assertTrue(st.data[0][0] > time.time() - st.check_delta)

    def test_check(self):
        st = module.ServiceTracker(self.work_path, min_runtime=40,
            requires_online=False, runtime_precision=10)

        now = time.time()
        st.data = [
            [now - 39, 1],
            [now - 29, 1],
            [now - 19, 1],
            [now - 10, 1],
            [now, 1],
        ]
        self.assertFalse(st.check())

        now = time.time()
        st.data = [
            [now - 40, 1],
            [now - 30, 1],
            [now - 20, 1],
            [now - 10, 1],
            [now, 1],
        ]
        self.assertFalse(st.check())

        now = time.time()
        st.data = [
            [now - 41, 1],
            [now - 31, 1],
            [now - 11, 1],
            [now - 1, 1],
        ]
        self.assertFalse(st.check())

        now = time.time()
        st.data = [
            [now - 41, 1],
            [now - 31, 1],
            [now - 21, 1],
            [now - 11, 1],
            [now - 1, 1],
        ]
        self.assertTrue(st.check())

    def test_check_online(self):
        st = module.ServiceTracker(self.work_path, min_runtime=40,
            requires_online=True, runtime_precision=10)

        now = time.time()
        st.data = [
            [now - 41, 1],
            [now - 31, 1],
            [now - 21, 0],
            [now - 11, 1],
            [now - 1, 1],
        ]
        self.assertFalse(st.check())

        now = time.time()
        st.data = [
            [now - 41, 1],
            [now - 31, 1],
            [now - 21, 1],
            [now - 11, 1],
            [now - 1, 1],
        ]
        self.assertTrue(st.check())


class MustRunTestCase(unittest.TestCase):
    def setUp(self):
        self.target = int
        self.work_path = WORK_PATH

    def test_run(self):
        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_get_ts.return_value = time.time() - 1
            mock_cpu_percent.return_value = 1
            self.assertFalse(module.Service(
                target=self.target,
                work_path=self.work_path,
                run_delta=10,
            )._must_run())

        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_get_ts.return_value = time.time() - 11
            mock_cpu_percent.return_value = 1
            self.assertTrue(module.Service(
                target=self.target,
                work_path=self.work_path,
                run_delta=10,
            )._must_run())

    def test_cpu_percent(self):
        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_get_ts.return_value = time.time() - 11
            mock_cpu_percent.return_value = 20
            self.assertFalse(module.Service(
                target=self.target,
                work_path=self.work_path,
                run_delta=10,
                force_run_delta=20,
                max_cpu_percent=10,
            )._must_run())

        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_get_ts.return_value = time.time() - 11
            mock_cpu_percent.return_value = 1
            self.assertTrue(module.Service(
                target=self.target,
                work_path=self.work_path,
                run_delta=10,
                force_run_delta=20,
                max_cpu_percent=10,
            )._must_run())

    def test_force_run(self):
        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_get_ts.return_value = time.time() - 11
            mock_cpu_percent.return_value = 20
            self.assertFalse(module.Service(
                target=self.target,
                work_path=self.work_path,
                run_delta=10,
                force_run_delta=20,
                max_cpu_percent=10,
            )._must_run())

        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_get_ts.return_value = time.time() - 21
            mock_cpu_percent.return_value = 20
            self.assertTrue(module.Service(
                target=self.target,
                work_path=self.work_path,
                run_delta=10,
                force_run_delta=20,
                max_cpu_percent=10,
            )._must_run())


class TargetTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)

    def test_run_once(self):
        self.res = False

        def target(p1, p2, p3=None):
            print((p1, p2, p3))
            self.res = p1 == 1 and p2 == 2 and p3 == 3

        svc = module.Service(
            target=target,
            args=(1, 2),
            kwargs={'p3': 3},
            work_path=WORK_PATH,
            run_delta=1,
        )
        svc.run_once()
        self.assertTrue(self.res)


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)

    def test_run_once(self):
        self.attempts = 0
        self.runs = 0

        def target():
            self.runs += 1

        svc = module.Service(
            target=target,
            work_path=WORK_PATH,
            run_delta=1,
        )
        end_ts = time.time() + 3
        with patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_cpu_percent.return_value = 1
            while time.time() < end_ts:
                svc.run_once()
                self.attempts += 1
                time.sleep(.2)
        print(f'{self.attempts=}, {self.runs=}')
        self.assertTrue(self.attempts >= 10)
        self.assertTrue(self.runs <= 4)

    def test_run_exc(self):
        self.result_path = os.path.join(WORK_PATH, '_test_result')

        def target():
            with open(self.result_path, 'a') as fd:
                fd.write('call\n')
            raise Exception('failed')

        def run():
            with patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
                mock_cpu_percent.return_value = 1
                svc = module.Service(
                    target=target,
                    work_path=WORK_PATH,
                    run_delta=1,
                    daemon_run_delta=.2,
                )
                svc.run()

        proc = Process(target=run)
        proc.start()
        time.sleep(3)
        os.kill(proc.pid, signal.SIGTERM)

        with open(self.result_path) as fd:
            lines = fd.read().splitlines()
        print(lines)
        self.assertEqual(lines, ['call'] * 3)

    def test_run(self):
        self.result_path = os.path.join(WORK_PATH, '_test_result')

        def target():
            with open(self.result_path, 'a') as fd:
                fd.write('call\n')

        def run():
            with patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
                mock_cpu_percent.return_value = 1
                svc = module.Service(
                    target=target,
                    work_path=WORK_PATH,
                    run_delta=1,
                    daemon_run_delta=.2,
                )
                svc.run()

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
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)

    def test_offline(self):
        self.runs = 0

        def target():
            self.runs += 1

        svc = module.Service(
            target=target,
            work_path=WORK_PATH,
            run_delta=1,
            min_runtime=5,
            requires_online=True,
        )
        with patch.object(psutil, 'cpu_percent') as mock_cpu_percent, \
                patch.object(module, 'is_online') as mock_is_online:
            mock_cpu_percent.return_value = 1
            mock_is_online.return_value = False
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
            work_path=WORK_PATH,
            run_delta=1,
            min_runtime=5,
            requires_online=True,
        )
        with patch.object(psutil, 'cpu_percent') as mock_cpu_percent:
            mock_cpu_percent.return_value = 1
            end_ts = time.time() + 7
            while time.time() < end_ts:
                svc.run_once()
                time.sleep(1)
        self.assertTrue(self.runs)
