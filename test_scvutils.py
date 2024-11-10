import os
from pprint import pprint
import shutil
import time
import unittest
from unittest.mock import patch

import svcutils as module


TEST_DIR = '_test_svcutils'
WORK_PATH = os.path.join(os.path.expanduser('~'), TEST_DIR)


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def makedirs(x):
    if not os.path.exists(x):
        os.makedirs(x)


class ServiceTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)
        self.runs = 0
        self.calls = 0

    def test_task(self):

        def callable():
            self.calls += 1

        task = module.Task(
            callable=callable,
            work_path=WORK_PATH,
            run_delta=1,
        )
        end_ts = time.time() + 3
        with patch.object(module, 'is_idle') as mock__is_idle:
            mock__is_idle.return_value = True
            while time.time() < end_ts:
                task.run()
                self.runs += 1
                time.sleep(.1)
        self.assertTrue(self.runs >= 30)
        self.assertTrue(self.calls <= 4)


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
