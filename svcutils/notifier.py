import json
import logging
import os
import subprocess
import sys

from svcutils.service import get_display_env


logger = logging.getLogger(__name__)


class WindowsNotifier:
    def send(self, title, body, app_name=None, on_click=None, **kwargs):
        from win11toast import notify as _notify
        _notify(title=title, body=body, app_id=app_name, on_click=on_click)


class LinuxNotifier:
    meta_filename = 'notifier.json'

    def get_meta(self, work_dir):
        if not work_dir:
            return {}
        meta_file = os.path.join(work_dir, self.meta_filename)
        if not os.path.exists(meta_file):
            return {}
        with open(meta_file) as fd:
            return json.load(fd)

    def set_meta(self, work_dir, meta):
        if not work_dir:
            return
        meta_file = os.path.join(work_dir, self.meta_filename)
        with open(meta_file, 'w') as fd:
            json.dump(meta, fd)

    def send(self, title, body, app_name=None, on_click=None, replace_key=None, work_dir=None, **kwargs):
        env = os.environ.copy()
        if not env.get('DISPLAY'):
            env.update(get_display_env())
        if on_click:
            body = f'{body} {on_click}'
        base_cmd = ['notify-send']
        if app_name:
            base_cmd += ['--app-name', app_name]
        cmd = base_cmd
        meta = self.get_meta(work_dir)
        if replace_key:
            cmd += ['--print-id']
            replace_id = meta.get(replace_key)
            if replace_id:
                cmd += ['--replace-id', replace_id]
        try:
            stdout = subprocess.check_output(cmd + [title, body], env=env)
        except subprocess.CalledProcessError:
            stdout = subprocess.check_output(base_cmd + [title, body], env=env)
        else:
            if replace_key:
                meta[replace_key] = stdout.decode('utf-8').strip()
                self.set_meta(work_dir, meta)


def notify(*args, **kwargs):
    try:
        {'win32': WindowsNotifier,
         'linux': LinuxNotifier}[sys.platform]().send(*args, **kwargs)
    except Exception:
        logger.exception('failed to send notification')
