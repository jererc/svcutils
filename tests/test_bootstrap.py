import os
import shutil
import unittest
from unittest.mock import patch

from svcutils import bootstrap as module


WORK_PATH = os.path.join(os.path.expanduser('~'), '_test_svcutils')


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
        return module.Bootstrapper(name='name', script_module='main',
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


class TaskTestCase(unittest.TestCase):
    def test_1(self):
        args = {
            'name': 'name',
            'script_module': 'module.main',
            'script_args': ['arg', '--flag'],
        }
        bs = module.Bootstrapper(**args)
        self.assertEqual(bs.venv_path, os.path.join(os.path.expanduser('~'),
            bs.venv_dir, args['name']))
        bin_dirname = 'Scripts' if os.name == 'nt' else 'bin'
        pip_filename = 'pip.exe' if os.name == 'nt' else 'pip'
        py_filename = 'pythonw.exe' if os.name == 'nt' else 'python'
        self.assertEqual(bs.pip_path, os.path.join(os.path.expanduser('~'),
            bs.venv_dir, args['name'], bin_dirname, pip_filename))
        self.assertEqual(bs.svc_py_path, os.path.join(os.path.expanduser('~'),
            bs.venv_dir, args['name'], bin_dirname, py_filename))

        with patch.object(bs, 'setup_venv'), \
                patch('builtins.input', return_value=''), \
                patch.object(bs, '_setup_windows_task'
                    ) as mock__setup_windows_task, \
                patch.object(bs, '_setup_linux_task'
                    ) as mock__setup_linux_task:
            bs.setup_task()
            if os.name == 'nt':
                cmd = mock__setup_windows_task.call_args_list[0].kwargs['cmd']
            else:
                cmd = mock__setup_linux_task.call_args_list[0].kwargs['cmd']
            cmd = cmd.split(' ')
            print(cmd)
            self.assertEqual(cmd[1:], ['-m', args['script_module']]
                + args['script_args'])
