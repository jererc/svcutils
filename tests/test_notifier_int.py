import os
import shutil
import time
import unittest

from tests import WORK_DIR
from svcutils import notifier as module


def remove_path(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


class NotifierTestCase(unittest.TestCase):
    def setUp(self):
        remove_path(WORK_DIR)
        os.makedirs(WORK_DIR)

    def test_1(self):
        for i in range(3):
            module.notify(f'title{i}', 'body', replace_key='title', work_dir=WORK_DIR)
            time.sleep(1)
