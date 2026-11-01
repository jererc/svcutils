import os
import shutil
import sys
import unittest
from unittest.mock import Mock, patch

from tests import WORK_DIR
from svcutils import bootstrap as module

module.HOME_DIR = WORK_DIR
module.ADMIN_DIR = WORK_DIR
module.APP_DATA_DIR = WORK_DIR
module.APP_DIR = WORK_DIR
NAME = '__TEST__'


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def get_bs(*args, **kwargs):
    with patch.object(module.Bootstrapper, '_setup'):
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


@unittest.skipUnless(sys.platform == 'linux', 'linux only')
class EnsureVenvSupportTestCase(unittest.TestCase):
    def setUp(self):
        self.package = f'python{sys.version_info.major}.{sys.version_info.minor}-venv'

    def _run(self, euid=1000, apt_get='/usr/bin/apt-get'):
        with patch.dict(sys.modules, {'ensurepip': None}), \
             patch.object(module.os, 'geteuid', return_value=euid), \
             patch.object(module.shutil, 'which', return_value=apt_get), \
             patch.object(module.subprocess, 'check_call') as mock_check_call:
            module.ensure_venv_support()
        return [c.args[0] for c in mock_check_call.call_args_list]

    def test_already_available(self):
        with patch.dict(sys.modules, {'ensurepip': object()}), \
             patch.object(module.subprocess, 'check_call') as mock_check_call:
            module.ensure_venv_support()
        mock_check_call.assert_not_called()

    def test_user_install(self):
        self.assertEqual(self._run(), [['sudo', 'apt-get', 'update'],
                                       ['sudo', 'apt-get', 'install', '-y', self.package]])

    def test_root_install(self):
        self.assertEqual(self._run(euid=0), [['apt-get', 'update'],
                                             ['apt-get', 'install', '-y', self.package]])

    def test_no_apt_get(self):
        with self.assertRaises(SystemExit) as ctx:
            self._run(apt_get=None)
        self.assertIn(self.package, str(ctx.exception))


class SetupVenvTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.bs = get_bs(name=NAME)
        os.makedirs(self.bs.venv_dir)
        self.parent = Mock()
        self.patchers = [patch.object(module, 'ensure_venv_support', self.parent.ensure_venv_support),
                         patch.object(module.subprocess, 'check_call', self.parent.check_call)]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_checked_before_creating_venv(self):
        self.bs._setup_venv()
        self.assertEqual([c[0] for c in self.parent.mock_calls], ['ensure_venv_support', 'check_call'])

    def test_not_checked_when_initialized(self):
        self.bs._setup_venv()
        self.parent.reset_mock()
        self.bs._setup_venv()
        self.parent.ensure_venv_support.assert_not_called()


class BootstrapperTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.bs = get_bs(name=NAME)

    def test_attrs(self):
        dirname = f'.{self.bs.name}'
        self.assertEqual(self.bs.work_dir, os.path.join(module.HOME_DIR, dirname))
        self.assertEqual(self.bs.venv_dir, os.path.join(module.HOME_DIR, dirname, module.VENV_DIRNAME))
        bin_dirname = 'Scripts' if sys.platform == 'win32' else 'bin'
        pip_filename = 'pip.exe' if sys.platform == 'win32' else 'pip'
        svc_py_filename = 'pythonw.exe' if sys.platform == 'win32' else 'python'
        py_filename = 'python.exe' if sys.platform == 'win32' else 'python'
        self.assertEqual(self.bs.pip_path, os.path.join(module.HOME_DIR, dirname, module.VENV_DIRNAME, bin_dirname, pip_filename))
        self.assertEqual(self.bs.svc_py_path, os.path.join(module.HOME_DIR, dirname, module.VENV_DIRNAME, bin_dirname, svc_py_filename))
        self.assertEqual(self.bs.py_path, os.path.join(module.HOME_DIR, dirname, module.VENV_DIRNAME, bin_dirname, py_filename))

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
