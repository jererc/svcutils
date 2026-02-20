from copy import deepcopy
import json
import logging
import os
import socket
import subprocess
import sys

import requests

from svcutils.service import get_display_env

logger = logging.getLogger(__name__)


class BaseNotifier:
    def __init__(self, app_name=None):
        self.app_name = app_name

    def send(self, title, body, on_click=None, replace_key=None):
        raise NotImplementedError()

    def clear(self, replace_key):
        raise NotImplementedError()


class WindowsNotifier(BaseNotifier):
    def send(self, title, body, on_click=None, replace_key=None):
        from win11toast import notify as _notify
        # if replace_key:
        #     self.clear(replace_key)
        try:
            _notify(title=title, body=body, app_id=self.app_name, on_click=on_click, tag=replace_key, group=self.app_name)
        except Exception:
            logger.exception(f'failed to send notification for {self.app_name=}')

    def clear(self, replace_key):
        from win11toast import clear_toast
        try:
            clear_toast(app_id=self.app_name, tag=replace_key, group=self.app_name)
        except Exception:
            logger.exception(f'failed to clear notification for {self.app_name=} {replace_key=}')


class LinuxNotifier(BaseNotifier):
    meta_file = os.path.expanduser('~/.notifier.json')

    def get_meta(self):
        if not os.path.exists(self.meta_file):
            return {}
        with open(self.meta_file) as f:
            return json.load(f)

    def set_meta(self, meta):
        with open(self.meta_file, 'w') as f:
            json.dump(meta, f, indent=4, sort_keys=True)

    def send(self, title, body, on_click=None, replace_key=None):
        env = os.environ.copy()
        if not env.get('DISPLAY'):
            env.update(get_display_env())
        if on_click:
            body = f'{body} {on_click}'
        base_cmd = ['notify-send']
        if self.app_name:
            base_cmd += ['--app-name', self.app_name]
        cmd = deepcopy(base_cmd)
        meta = self.get_meta()
        if self.app_name and replace_key:
            cmd += ['--print-id']
            replace_id = meta.get(self.app_name, {}).get(replace_key)
            if replace_id:
                cmd += ['--replace-id', replace_id]
        try:
            stdout = subprocess.check_output(cmd + [title, body], env=env)
        except subprocess.CalledProcessError:
            try:
                stdout = subprocess.check_output(base_cmd + [title, body], env=env)
            except subprocess.CalledProcessError:
                logger.exception(f'failed to send notification for {self.app_name=}')
        else:
            if self.app_name and replace_key:
                meta.setdefault(self.app_name, {})
                meta[self.app_name][replace_key] = stdout.decode('utf-8').strip()
                self.set_meta(meta)

    def clear(self, replace_key):
        env = os.environ.copy()
        if not env.get('DISPLAY'):
            env.update(get_display_env())
        meta = self.get_meta()
        replace_id = meta.get(self.app_name, {}).get(replace_key)
        if not replace_id:
            logger.warning('no replace_id found')
            return
        cmd = ['notify-send', '--app-name', self.app_name, '--replace-id', replace_id, '--transient', ' ']
        try:
            subprocess.check_output(cmd, env=env, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logger.warning(f'failed to clear notification for {self.app_name=} {replace_key=}: {e.output}')


class TelegramNotifier(BaseNotifier):
    def __init__(self, bot_token, chat_id, app_name=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.app_name = app_name

    def send(self, title, body, on_click=None, **kwargs):
        url = f'https://api.telegram.org/bot{self.bot_token}/sendMessage'
        on_click_text = f'\n{on_click}' if on_click else ''
        payload = {
            'chat_id': self.chat_id,
            'text': f'<b>{self.app_name or ""}@{socket.gethostname()}: {title}</b>\n{body}{on_click_text}',
            'parse_mode': 'HTML',
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception:
            logger.exception(f'failed to send notification for {self.app_name=}')


def get_notifier(app_name=None, telegram_bot_token=None, telegram_chat_id=None):
    if telegram_bot_token and telegram_chat_id:
        return TelegramNotifier(bot_token=telegram_bot_token, chat_id=telegram_chat_id, app_name=app_name)
    return {'linux': LinuxNotifier, 'win32': WindowsNotifier}[sys.platform](app_name=app_name)
