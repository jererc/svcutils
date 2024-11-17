import os
import shutil
import time
import unittest

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
    def test_1(self):
        bs = module.Bootstrapper(name='name', script_path=__file__,
            schedule_mins=1)
        self.assertEqual(bs._generate_crontab_schedule(), '* * * * *')

    def test_2(self):
        bs = module.Bootstrapper(name='name', script_path=__file__,
            schedule_mins=15)
        self.assertEqual(bs._generate_crontab_schedule(), '*/15 * * * *')

    def test_3(self):
        bs = module.Bootstrapper(name='name', script_path=__file__,
            schedule_mins=60 * 2 + 1)
        self.assertEqual(bs._generate_crontab_schedule(), '0 */2 * * *')

    def test_4(self):
        bs = module.Bootstrapper(name='name', script_path=__file__,
            schedule_mins=24 * 60 + 1)
        self.assertEqual(bs._generate_crontab_schedule(), '0 0 * * *')


class BootstrapperTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_PATH)
        makedirs(WORK_PATH)

    def test_1(self):
        args = {
            'name': 'savegame',
            'target_url': 'https://raw.githubusercontent.com/jererc/savegame/refs/heads/main/scripts/run.py',
            'target_dir': WORK_PATH,
            'target_args': ['save', '--task'],
        }
        bs = module.Bootstrapper(**args)
        self.assertTrue(os.path.exists(bs.target_file))
        mtime1 = os.stat(bs.target_file).st_mtime
        with open(bs.target_file) as fd:
            content1 = fd.read()
        self.assertTrue(content1)

        time.sleep(.5)
        bs2 = module.Bootstrapper(**args)
        self.assertTrue(os.path.exists(bs2.target_file))
        mtime2 = os.stat(bs2.target_file).st_mtime
        with open(bs.target_file) as fd:
            content2 = fd.read()
        self.assertTrue(content2)

        self.assertEqual(content2, content1)
        self.assertEqual(mtime2, mtime1)
        cmd = bs._get_cmd()
        self.assertEqual(cmd.split(' ')[1:],
            [bs.target_file] + args['target_args'])
