import logging
from multiprocessing import Process
import os
from pprint import pprint
import shutil
import signal
import time
import unittest
from unittest.mock import patch

import svcutils as module


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


class MustRunTestCase(unittest.TestCase):
    def setUp(self):
        self.callable = int
        self.work_path = WORK_PATH

    def test_run(self):
        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(module, 'is_idle') as mock_is_idle:
            mock_get_ts.return_value = time.time() - 1
            mock_is_idle.return_value = True
            self.assertFalse(module.Service(
                callable=self.callable,
                work_path=self.work_path,
                run_delta=10,
            )._must_run())

        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(module, 'is_idle') as mock_is_idle:
            mock_get_ts.return_value = time.time() - 20
            mock_is_idle.return_value = True
            self.assertTrue(module.Service(
                callable=self.callable,
                work_path=self.work_path,
                run_delta=10,
            )._must_run())

    def test_force_run(self):
        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(module, 'is_idle') as mock_is_idle:
            mock_get_ts.return_value = time.time() - 15
            mock_is_idle.return_value = False
            self.assertFalse(module.Service(
                callable=self.callable,
                work_path=self.work_path,
                run_delta=10,
                force_run_delta=20,
            )._must_run())

        with patch.object(module.RunFile, 'get_ts') as mock_get_ts, \
                patch.object(module, 'is_idle') as mock_is_idle:
            mock_get_ts.return_value = time.time() - 30
            mock_is_idle.return_value = False
            self.assertTrue(module.Service(
                callable=self.callable,
                work_path=self.work_path,
                run_delta=10,
                force_run_delta=20,
            )._must_run())


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)

    def test_run_once(self):
        self.attempts = 0
        self.runs = 0

        def callable():
            self.runs += 1

        svc = module.Service(
            callable=callable,
            work_path=WORK_PATH,
            run_delta=1,
        )
        end_ts = time.time() + 3
        with patch.object(module, 'is_idle') as mock_is_idle:
            mock_is_idle.return_value = True
            while time.time() < end_ts:
                svc.run_once()
                self.attempts += 1
                time.sleep(.2)
        print(f'{self.attempts=}, {self.runs=}')
        self.assertTrue(self.attempts >= 10)
        self.assertTrue(self.runs <= 4)

    def test_run_exc(self):
        self.result_path = os.path.join(WORK_PATH, '_test_result')

        def callable():
            with open(self.result_path, 'a') as fd:
                fd.write('call\n')
            raise Exception('failed')

        def run():
            with patch.object(module, 'is_idle') as mock_is_idle:
                mock_is_idle.return_value = True
                svc = module.Service(
                    callable=callable,
                    work_path=WORK_PATH,
                    run_delta=1,
                    loop_delay=.2,
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

        def callable():
            with open(self.result_path, 'a') as fd:
                fd.write('call\n')

        def run():
            with patch.object(module, 'is_idle') as mock_is_idle:
                mock_is_idle.return_value = True
                svc = module.Service(
                    callable=callable,
                    work_path=WORK_PATH,
                    run_delta=1,
                    loop_delay=.2,
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


class RunningTimeTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)

    def test_offline(self):
        self.runs = 0

        def callable():
            self.runs += 1

        svc = module.Service(
            callable=callable,
            work_path=WORK_PATH,
            run_delta=1,
            min_running_time=5,
            requires_online=True,
        )
        with patch.object(module, 'is_idle') as mock_is_idle, \
                patch.object(module, 'is_online') as mock_is_online:
            mock_is_idle.return_value = True
            mock_is_online.return_value = False
            end_ts = time.time() + 7
            while time.time() < end_ts:
                svc.run_once()
                time.sleep(1)
        self.assertFalse(self.runs)

    def test_online(self):
        self.runs = 0

        def callable():
            self.runs += 1

        svc = module.Service(
            callable=callable,
            work_path=WORK_PATH,
            run_delta=1,
            min_running_time=5,
            requires_online=True,
        )
        with patch.object(module, 'is_idle') as mock_is_idle:
            mock_is_idle.return_value = True
            end_ts = time.time() + 7
            while time.time() < end_ts:
                svc.run_once()
                time.sleep(1)
        self.assertTrue(self.runs)


class BootstrapTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)

    def test_1(self):
        module.Bootstrapper(
            script_path=os.path.realpath(__file__),
            linux_args=['save', '--task'],
            windows_args=['save', '--daemon'],
        ).run()
