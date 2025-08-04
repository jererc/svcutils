import time
import unittest

import tests
from svcutils import notifier as module


class NotifierTestCase(unittest.TestCase):
    def test_1(self):
        for i in range(3):
            module.notify(f'title{i}', 'body', app_name='app', replace_key='title')
            time.sleep(1)
        module.clear_notif(app_name='app', replace_key='title')
