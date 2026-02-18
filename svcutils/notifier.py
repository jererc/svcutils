from copy import deepcopy
import json
import logging
import os
import subprocess
import sys

import requests

from svcutils.service import get_display_env

logger = logging.getLogger(__name__)


class WindowsNotifier:
    def send(self, title, body, app_name=None, on_click=None, replace_key=None):
        from win11toast import notify as _notify
        # if replace_key:
        #     self.clear(app_name, replace_key)
        _notify(title=title, body=body, app_id=app_name, on_click=on_click,
                tag=replace_key, group=app_name)

    def clear(self, app_name, replace_key):
        from win11toast import clear_toast
        try:
            clear_toast(app_id=app_name, tag=replace_key, group=app_name)
        except Exception:
            logger.exception(f'failed to clear notification for {app_name=} {replace_key=}')


class LinuxNotifier:
    meta_file = os.path.expanduser('~/.notifier.json')

    def get_meta(self):
        if not os.path.exists(self.meta_file):
            return {}
        with open(self.meta_file) as f:
            return json.load(f)

    def set_meta(self, meta):
        with open(self.meta_file, 'w') as f:
            json.dump(meta, f, indent=4, sort_keys=True)

    def send(self, title, body, app_name=None, on_click=None, replace_key=None):
        env = os.environ.copy()
        if not env.get('DISPLAY'):
            env.update(get_display_env())
        if on_click:
            body = f'{body} {on_click}'
        base_cmd = ['notify-send']
        if app_name:
            base_cmd += ['--app-name', app_name]
        cmd = deepcopy(base_cmd)
        meta = self.get_meta()
        if app_name and replace_key:
            cmd += ['--print-id']
            replace_id = meta.get(app_name, {}).get(replace_key)
            if replace_id:
                cmd += ['--replace-id', replace_id]
        try:
            stdout = subprocess.check_output(cmd + [title, body], env=env)
        except subprocess.CalledProcessError:
            stdout = subprocess.check_output(base_cmd + [title, body], env=env)
        else:
            if app_name and replace_key:
                meta.setdefault(app_name, {})
                meta[app_name][replace_key] = stdout.decode('utf-8').strip()
                self.set_meta(meta)

    def clear(self, app_name, replace_key):
        env = os.environ.copy()
        if not env.get('DISPLAY'):
            env.update(get_display_env())
        meta = self.get_meta()
        replace_id = meta.get(app_name, {}).get(replace_key)
        if not replace_id:
            logger.warning('no replace_id found')
            return
        cmd = ['notify-send', '--app-name', app_name, '--replace-id', replace_id, '--transient', ' ']
        try:
            subprocess.check_output(cmd, env=env, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            logger.warning(f'failed to clear notification for {app_name=} {replace_key=}: {e.output}')


class TelegramNotifier:
    def __init__(self, telegram_bot_token, telegram_chat_id):
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id

    def send(self, title, body, **kwargs):
        url = f'https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage'
        payload = {
            'chat_id': self.telegram_chat_id,
            'text': f'{title}\n{body}',
        }
        requests.post(url, json=payload, timeout=10)


def notify(*args, **kwargs):
    telegram_bot_token = kwargs.pop('telegram_bot_token', None)
    telegram_chat_id = kwargs.pop('telegram_chat_id', None)
    if telegram_bot_token and telegram_chat_id:
        try:
            return TelegramNotifier(telegram_bot_token, telegram_chat_id).send(*args, **kwargs)
        except Exception:
            logger.exception('failed to send notification via telegram')
    try:
        return {'linux': LinuxNotifier, 'win32': WindowsNotifier}[sys.platform]().send(*args, **kwargs)
    except Exception:
        logger.exception('failed to send desktop notification')


def clear_notification(*args, **kwargs):
    try:
        return {'linux': LinuxNotifier, 'win32': WindowsNotifier}[sys.platform]().clear(*args, **kwargs)
    except Exception:
        logger.exception('failed to clear desktop notification')
