import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request


VENV_DIRNAME = 'venv'
VENV_BIN_DIRNAME = {'nt': 'Scripts', 'posix': 'bin'}[os.name]
VENV_PIP_PATH = {'nt': 'pip.exe', 'posix': 'pip'}[os.name]
VENV_PY_PATH = {'nt': 'python.exe', 'posix': 'python'}[os.name]
VENV_SVC_PY_PATH = {'nt': 'pythonw.exe', 'posix': 'python'}[os.name]
ADMIN_DIR = {
    'nt': os.environ.get('WINDIR', r'C:\Windows'),
    'posix': '/root',
}[os.name]


def is_relative_to(target_path, base_path):
    target = Path(target_path).resolve()
    base = Path(base_path).resolve()
    return target.is_relative_to(base)


def get_valid_cwd():
    path = os.getcwd()
    if is_relative_to(path, ADMIN_DIR):
        raise SystemExit(f'invalid working dir {path}')
    return path


def makedirs(path):
    if not os.path.exists(path):
        os.makedirs(path)


def get_app_dir(name):
    if os.name == 'nt':
        root = os.getenv('APPDATA', os.path.join(os.path.expanduser('~'),
            'AppData', 'Roaming'))
    else:
        root = os.getenv('HOME', os.path.join(os.path.expanduser('~'),
            '.local', 'share'))
    path = os.path.join(root, name)
    makedirs(path)
    return path


def get_work_dir(name):
    path = os.path.join(os.path.expanduser('~'), f'.{name}')
    makedirs(path)
    return path


class Bootstrapper:
    def __init__(self, name, cmd_args=None, install_requires=None,
                 force_reinstall=False, init_cmds=None, extra_cmds=None,
                 download_assets=None, schedule_minutes=2):
        self.name = name
        self.cmd_args = cmd_args
        self.install_requires = install_requires
        self.force_reinstall = force_reinstall
        self.init_cmds = init_cmds
        self.extra_cmds = extra_cmds
        self.schedule_minutes = schedule_minutes
        self.download_assets = download_assets
        self.cwd = get_valid_cwd()
        self.work_dir = get_work_dir(self.name)
        self.venv_dir = os.path.join(self.work_dir, VENV_DIRNAME)
        self.venv_bin_dir = os.path.join(self.venv_dir, VENV_BIN_DIRNAME)
        self.pip_path = os.path.join(self.venv_bin_dir, VENV_PIP_PATH)
        self.py_path = os.path.join(self.venv_bin_dir, VENV_PY_PATH)
        self.svc_py_path = os.path.join(self.venv_bin_dir, VENV_SVC_PY_PATH)

    def _run_venv_cmds(self, cmds):
        for cmd in cmds:
            venv_cmd = [self.py_path, '-m'] + cmd
            print(f'running {" ".join(venv_cmd)}')
            subprocess.check_call(venv_cmd)

    def setup_venv(self):
        requires_init = not os.path.exists(self.pip_path)
        if requires_init:
            subprocess.check_call([sys.executable, '-m', 'venv',
                self.venv_dir])   # requires python3-venv
            print(f'created the virtualenv {self.venv_dir}')
        if self.install_requires:
            base_cmd = [self.pip_path, 'install']
            if self.force_reinstall:
                base_cmd.append('--force-reinstall')
            subprocess.check_call(base_cmd + self.install_requires)
        if requires_init and self.init_cmds:
            self._run_venv_cmds(self.init_cmds)
        if self.extra_cmds:
            self._run_venv_cmds(self.extra_cmds)

    def _download_assets(self):
        if not self.download_assets:
            return
        for filename, url in self.download_assets:
            file = os.path.join(self.cwd, filename)
            if not os.path.exists(file):
                urllib.request.urlretrieve(url, file)
                print(f'created {file}')

    def _get_cmd(self):
        if not self.cmd_args:
            raise SystemExit('missing cmd_args')
        return [self.svc_py_path, '-m'] + self.cmd_args

    def _generate_crontab_schedule(self):
        match self.schedule_minutes:
            case _ if self.schedule_minutes < 2:
                return '* * * * *'
            case _ if self.schedule_minutes < 60:
                return f'*/{self.schedule_minutes} * * * *'
            case _ if self.schedule_minutes < 60 * 24:
                hours = self.schedule_minutes // 60
                if hours == 1:
                    return '0 * * * *'
                return f'0 */{hours} * * *'
            case _:
                return '0 0 * * *'

    def _setup_linux_crontab(self, cmd):
        res = subprocess.run(['crontab', '-l'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        current_crontab = res.stdout if res.returncode == 0 else ''
        new_job = f'{self._generate_crontab_schedule()} {cmd}\n'
        updated_crontab = ''
        job_found = False
        for line in current_crontab.splitlines():
            if self.svc_py_path in line:
                updated_crontab += new_job
                job_found = True
            else:
                updated_crontab += f'{line}\n'
        if not job_found:
            updated_crontab += new_job
        res = subprocess.run(['crontab', '-'], input=updated_crontab,
            text=True)
        if res.returncode != 0:
            raise SystemExit('failed to update crontab')
        print(f'created the crontab job {new_job.strip()}')

    def _setup_windows_task(self, cmd, task_name):
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            raise SystemExit('must run as admin to update scheduled tasks')
        subprocess.check_call(['schtasks', '/create',
            '/tn', task_name,
            '/tr', cmd,
            '/sc', 'minute',
            '/mo', str(self.schedule_minutes),
            '/rl', 'highest',
            '/f',
        ])
        # subprocess.check_call(['schtasks', '/run',
        #     '/tn', task_name])
        print(f'created the task {task_name}')

    def _create_linux_shortcut(self, name, cmd, shortcut_path,
            description=''):
        makedirs(os.path.dirname(shortcut_path))
        content = f"""[Desktop Entry]
Type=Application
Name={name}
Exec={cmd}
Terminal=true
Comment={description}
"""
        with open(shortcut_path, 'w') as fd:
            fd.write(content)
        return shortcut_path

    def _create_windows_shortcut(self, target_path, shortcut_path,
            arguments='', working_dir='', description=''):
        if not working_dir:
            working_dir = os.path.dirname(target_path)
        vbs_content = f"""Set objShell = WScript.CreateObject("WScript.Shell")
Set objShortcut = objShell.CreateShortcut("{shortcut_path}")
objShortcut.TargetPath = "{target_path}"
objShortcut.Arguments = "{arguments}"
objShortcut.WorkingDirectory = "{working_dir}"
objShortcut.Description = "{description}"
objShortcut.Save
"""
        with tempfile.NamedTemporaryFile('w', delete=False, suffix='.vbs'
                ) as temp_file:
            temp_file.write(vbs_content)
            temp_vbs_path = temp_file.name
        try:
            os.system(f'cscript //NoLogo "{temp_vbs_path}"')
        finally:
            os.remove(temp_vbs_path)
        return shortcut_path

    def setup_shortcut(self):
        self.setup_venv()
        self._download_assets()
        cmd = self._get_cmd()
        if os.name == 'nt':
            file = self._create_windows_shortcut(
                target_path=cmd[0],
                shortcut_path=os.path.join(os.getenv('APPDATA'),
                    r'Microsoft\Windows\Start Menu\Programs',
                    f'{self.name}.lnk'),
                arguments=' '.join(cmd[1:]),
                working_dir=self.cwd,
                description=self.name,
            )
        else:
            file = self._create_linux_shortcut(
                name=self.name,
                cmd=' '.join(cmd),
                shortcut_path=os.path.join(os.path.expanduser('~'),
                    '.local/share/applications',
                    f'{self.name}.desktop'),
                description=self.name,
            )
        print(f'created shortcut {file}')

    def setup_task(self):
        self.setup_venv()
        self._download_assets()
        cmd = ' '.join(self._get_cmd())
        if os.name == 'nt':
            self._setup_windows_task(cmd=cmd, task_name=self.name)
        else:
            self._setup_linux_crontab(cmd=cmd)
