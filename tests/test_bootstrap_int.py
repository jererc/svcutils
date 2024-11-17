import os
import unittest

from svcutils import bootstrap as module


WORK_PATH = os.path.join(os.path.expanduser('~'), '_test_svcutils')


class BootstrapperTestCase(unittest.TestCase):
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
