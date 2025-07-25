import os
import shutil
import subprocess
import unittest
from unittest.mock import patch

from tests import WORK_DIR
from svcutils import bootstrap as module


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


class CrontabTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.name = '__TEST__'

    def _read_crontab(self):
        stdout = subprocess.check_output(['crontab', '-l']).decode('utf-8')
        return [r for r in stdout.splitlines() if self.name in r]

    def test_1(self):
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


class DownloadAssetsTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)
        self.name = '__TEST__'
        self.bs = module.Bootstrapper(
            name=self.name,
            cmd_args=['module.main', 'arg1', '--flag1'],
            download_assets=[
                ('user_settings.py', 'https://raw.githubusercontent.com/jererc/bodiez/refs/heads/main/bootstrap/user_settings.py'),
            ],
        )

    def test_1(self):
        with patch('os.getcwd', return_value=WORK_DIR):
            self.bs._download_assets()
        file = os.path.join(WORK_DIR, 'user_settings.py')
        self.assertTrue(os.path.exists(file))
        with open(file) as fd:
            content = fd.read()
        self.assertTrue(content)

        content2 = 'NEW CONTENT'
        with open(file, 'w') as fd:
            fd.write(content2)

        with patch('os.getcwd', return_value=WORK_DIR):
            self.bs._download_assets()
        self.assertTrue(os.path.exists(file))
        with open(file) as fd:
            content = fd.read()
        self.assertEqual(content, content2)
