from glob import glob
import os
import shutil
import unittest
from unittest.mock import patch

from svcutils import bootstrap as module


WORK_DIR = os.path.join(os.path.expanduser('~'), '_tests', 'svcutils')


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def makedirs(path):
    if not os.path.exists(path):
        os.makedirs(path)


class CrontabTestCase(unittest.TestCase):
    def _get_bs(self, schedule_minutes):
        return module.Bootstrapper(name='name', cmd_args=['main'],
            schedule_minutes=schedule_minutes)

    def test_1(self):
        bs = self._get_bs(schedule_minutes=1)
        self.assertEqual(bs._generate_crontab_schedule(), '* * * * *')

    def test_2(self):
        bs = self._get_bs(schedule_minutes=15)
        self.assertEqual(bs._generate_crontab_schedule(), '*/15 * * * *')

    def test_3(self):
        bs = self._get_bs(schedule_minutes=60 * 2 + 1)
        self.assertEqual(bs._generate_crontab_schedule(), '0 */2 * * *')

    def test_4(self):
        bs = self._get_bs(schedule_minutes=24 * 60 + 1)
        self.assertEqual(bs._generate_crontab_schedule(), '0 0 * * *')


class BootstrapperTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        makedirs(WORK_DIR)
        self.args = {
            'name': 'name',
            'cmd_args': ['module.main', 'arg', '--flag'],
        }
        with patch('os.path.expanduser', return_value=WORK_DIR):
            self.bs = module.Bootstrapper(**self.args)

    def test_cmd(self):
        bs = module.Bootstrapper(name='name')
        self.assertRaises(SystemExit, bs._get_cmd)

        bs = module.Bootstrapper(name='name', cmd_args=['module.main'])
        self.assertEqual(bs._get_cmd()[1:], ['-m', 'module.main'])

    def test_attrs(self):
        dirname = f'.{self.args["name"]}'
        self.assertEqual(self.bs.venv_dir, os.path.join(WORK_DIR,
            dirname, module.VENV_DIRNAME))
        bin_dirname = 'Scripts' if os.name == 'nt' else 'bin'
        pip_filename = 'pip.exe' if os.name == 'nt' else 'pip'
        py_filename = 'pythonw.exe' if os.name == 'nt' else 'python'
        self.assertEqual(self.bs.pip_path, os.path.join(WORK_DIR,
            dirname, module.VENV_DIRNAME, bin_dirname, pip_filename))
        self.assertEqual(self.bs.svc_py_path, os.path.join(WORK_DIR,
            dirname, module.VENV_DIRNAME, bin_dirname, py_filename))

    def test_task(self):
        with patch.object(self.bs, 'setup_venv'), \
                patch.object(self.bs, '_setup_windows_task'
                    ) as mock__setup_windows_task, \
                patch.object(self.bs, '_setup_linux_crontab'
                    ) as mock__setup_linux_crontab:
            self.bs.setup_task()
            if os.name == 'nt':
                cmd = mock__setup_windows_task.call_args_list[0].kwargs['cmd']
            else:
                cmd = mock__setup_linux_crontab.call_args_list[0].kwargs['cmd']
            cmd = cmd.split(' ')
            print(cmd)
            self.assertEqual(cmd[1:], ['-m'] + self.args['cmd_args'])
