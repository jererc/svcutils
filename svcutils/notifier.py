from copy import deepcopy
import json
import logging
import os
import subprocess
import sys

from svcutils.service import get_display_env


logger = logging.getLogger(__name__)


class WindowsNotifier:
    def send(self, title, body, app_name=None, on_click=None, replace_key=None, **kwargs):
        from win11toast import clear_toast, notify as _notify
        if replace_key:
            clear_toast(app_id=app_name, tag=replace_key, group=app_name)
        _notify(title=title, body=body, app_id=app_name, on_click=on_click,
                tag=replace_key, group=app_name)

    def clear(self, app_name, replace_key):
        from win11toast import clear_toast
        clear_toast(app_id=app_name, tag=replace_key, group=app_name)


class LinuxNotifier:
    meta_file = '/tmp/notifier.json'

    def get_meta(self):
        if not os.path.exists(self.meta_file):
            return {}
        with open(self.meta_file) as f:
            return json.load(f)

    def set_meta(self, meta):
        with open(self.meta_file, 'w') as f:
            json.dump(meta, f, indent=4, sort_keys=True)

    def send(self, title, body, app_name=None, on_click=None, replace_key=None, **kwargs):
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
            logger.warning(f'failed to clear notification: {e.output}')


def notify(*args, **kwargs):
    try:
        {'win32': WindowsNotifier,
         'linux': LinuxNotifier}[sys.platform]().send(*args, **kwargs)
    except Exception:
        logger.exception('failed to send notification')


def clear_notif(app_name, replace_key):
    try:
        {'win32': WindowsNotifier,
         'linux': LinuxNotifier}[sys.platform]().clear(app_name, replace_key)
    except Exception:
        logger.exception('failed to clear notification')
