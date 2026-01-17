import os
import shutil
import sys
import unittest
from unittest.mock import patch

from tests import WORK_DIR
from svcutils import bootstrap as module

NAME = '__TEST__'


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def get_bs(*args, **kwargs):
    with patch('os.makedirs'):
        return module.Bootstrapper(*args, **kwargs)


class CrontabTestCase(unittest.TestCase):
    def setUp(self):
        self.bs = get_bs(name=NAME, tasks=[{'name': 'test', 'args': ['main']}])

    def test_1(self):
        self.assertEqual(self.bs._generate_crontab_schedule(schedule_minutes=1), '* * * * *')

    def test_2(self):
        self.assertEqual(self.bs._generate_crontab_schedule(schedule_minutes=15), '*/15 * * * *')

    def test_3(self):
        self.assertEqual(self.bs._generate_crontab_schedule(schedule_minutes=60 * 2 + 1), '0 */2 * * *')

    def test_4(self):
        self.assertEqual(self.bs._generate_crontab_schedule(schedule_minutes=24 * 60 + 1), '0 0 * * *')


class BootstrapperTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.args = {
            'name': NAME,
            'tasks': [{'name': 'test', 'args': ['module.main', 'arg', '--flag']}],
        }
        self.bs = get_bs(**self.args)

    def test_attrs(self):
        dirname = f'.{self.args["name"]}'
        self.assertEqual(self.bs.venv_dir, os.path.join(os.path.expanduser('~'), dirname, module.VENV_DIRNAME))
        bin_dirname = 'Scripts' if sys.platform == 'win32' else 'bin'
        pip_filename = 'pip.exe' if sys.platform == 'win32' else 'pip'
        py_filename = 'pythonw.exe' if sys.platform == 'win32' else 'python'
        self.assertEqual(self.bs.pip_path, os.path.join(os.path.expanduser('~'), dirname, module.VENV_DIRNAME, bin_dirname, pip_filename))
        self.assertEqual(self.bs.svc_py_path, os.path.join(os.path.expanduser('~'), dirname, module.VENV_DIRNAME, bin_dirname, py_filename))

    def test_task(self):
        args = ['module.main', 'arg', '--flag']
        with patch.object(self.bs, '_setup_windows_task') as mock__setup_windows_task, \
             patch.object(self.bs, '_setup_linux_crontab') as mock__setup_linux_crontab:
            self.bs._setup_task(name='test', args=args)
            if sys.platform == 'win32':
                cmd = mock__setup_windows_task.call_args_list[0].kwargs['cmd']
            else:
                cmd = mock__setup_linux_crontab.call_args_list[0].kwargs['cmd']
            cmd = cmd.split(' ')
            print(cmd)
            self.assertEqual(cmd[1:], ['-m'] + args)
