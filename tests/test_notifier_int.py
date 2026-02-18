import json
import os.path
import time
import unittest

import tests
from svcutils import notifier as module

TELEGRAM_SETTINGS_FILE = os.path.expanduser('~/telegram.json')

class NotifierTestCase(unittest.TestCase):
    def test_1(self):
        for i in range(3):
            module.notify(f'title{i}', 'body', app_name='app', replace_key='title')
            time.sleep(1)
        module.clear_notification(app_name='app', replace_key='title')


class NotifierTelegramTestCase(unittest.TestCase):
    def setUp(self):
        with open(TELEGRAM_SETTINGS_FILE) as f:
            self.settings = json.load(f)

    def test_1(self):
        module.notify(
            'title',
            body='body',
            on_click='https://en.wikipedia.org',
            telegram_bot_token=self.settings['BOT_TOKEN'],
            telegram_chat_id=self.settings['CHAT_ID'],
        )
