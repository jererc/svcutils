import os
import shutil
import time
import unittest

from svcutils import notifier as module


WORK_DIR = os.path.join(os.path.expanduser('~'), '_tests', 'svcutils')


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


class NotifierTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR, exist_ok=True)

    def test_1(self):
        for i in range(3):
            module.notify(f'title{i}', 'body', replace_key='title', work_dir=WORK_DIR)
            time.sleep(1)
