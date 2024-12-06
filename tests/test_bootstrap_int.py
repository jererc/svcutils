import os
import shutil
import subprocess
import unittest

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
    def setUp(self):
        remove_path(WORK_DIR)
        makedirs(WORK_DIR)
        self.name = '__TEST__'

    def _read_crontab(self):
        stdout = subprocess.check_output(['crontab', '-l']).decode('utf-8')
        return [r for r in stdout.splitlines() if self.name in r]

    def test_crontab(self):
        bs = module.Bootstrapper(name=self.name,
            cmd_args=['module.main', 'arg1', '--flag1'])
        cmd = ' '.join(bs._get_cmd())
        bs._setup_linux_crontab(cmd)
        res = self._read_crontab()
        print(res)
        self.assertEqual(len(res), 1)
        self.assertTrue(cmd in res[0])

        bs = module.Bootstrapper(name=self.name,
            cmd_args=['module.main', 'arg2', '--flag1'])
        cmd = ' '.join(bs._get_cmd())
        bs._setup_linux_crontab(cmd)
        res = self._read_crontab()
        print(res)
        self.assertEqual(len(res), 1)
        self.assertTrue(cmd in res[0])

        bs = module.Bootstrapper(name=self.name,
            cmd_args=['module.main', 'arg2', '--flag2'])
        cmd = ' '.join(bs._get_cmd())
        bs._setup_linux_crontab(cmd)
        res = self._read_crontab()
        print(res)
        self.assertEqual(len(res), 1)
        self.assertTrue(cmd in res[0])
