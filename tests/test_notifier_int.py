import json
import os.path
import time
import unittest

import tests
from svcutils import notifier as module

TELEGRAM_SETTINGS_FILE = os.path.expanduser('~/telegram.json')


class DesktopTestCase(unittest.TestCase):
    def setUp(self):
        self.notifier = module.get_notifier(app_name='awesome-app')

    def test_1(self):
        for i in range(3):
            self.notifier.send(f'awesome title{i}', 'awesome body', replace_key='title')
            time.sleep(1)
        self.notifier.clear(replace_key='title')


class TelegramTestCase(unittest.TestCase):
    def setUp(self):
        with open(TELEGRAM_SETTINGS_FILE) as f:
            self.settings = json.load(f)
        self.notifier = module.get_notifier(
            app_name='awesome-app',
            telegram_bot_token=self.settings['BOT_TOKEN'],
            telegram_chat_id=self.settings['CHAT_ID'],
        )

    def test_1(self):
        self.notifier.send('awesome title', 'awesome body', on_click='https://en.wikipedia.org')
