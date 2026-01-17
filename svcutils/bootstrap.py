import ctypes
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

HOME_DIR = os.path.expanduser('~')
ADMIN_DIR = {'linux': '/root',
             'win32': os.getenv('WINDIR', r'C:\Windows')}[sys.platform]
APP_DATA_DIR = {'linux': os.path.join(os.getenv('HOME', HOME_DIR), '.local', 'share'),
                'win32': os.getenv('APPDATA', os.path.join(HOME_DIR, 'AppData', 'Roaming'))}[sys.platform]
APP_DIR = {'linux': os.path.join(APP_DATA_DIR, 'applications'),
           'win32': os.path.join(APP_DATA_DIR, r'Microsoft\Windows\Start Menu\Programs')}[sys.platform]
VENV_DIRNAME = 'venv'
VENV_BIN_DIRNAME = {'linux': 'bin', 'win32': 'Scripts'}[sys.platform]
VENV_PIP_PATH = {'linux': 'pip', 'win32': 'pip.exe'}[sys.platform]
VENV_PY_PATH = {'linux': 'python', 'win32': 'python.exe'}[sys.platform]
VENV_SVC_PY_PATH = {'linux': 'python', 'win32': 'pythonw.exe'}[sys.platform]


def get_valid_cwd():
    path = os.getcwd()
    if Path(path).resolve().is_relative_to(Path(ADMIN_DIR).resolve()):
        raise SystemExit(f'Error: invalid working dir {path}')
    return path


def get_app_dir(name):
    path = os.path.join(APP_DATA_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path


def get_work_dir(name):
    path = os.path.join(HOME_DIR, f'.{name}')
    os.makedirs(path, exist_ok=True)
    return path


class Bootstrapper:
    def __init__(self, name, install_requires=None, force_reinstall=False, init_cmds=None, extra_cmds=None,
                 tasks=None, shortcuts=None, download_assets=None):
        self.name = name
        self.install_requires = install_requires
        self.force_reinstall = force_reinstall
        self.init_cmds = init_cmds
        self.extra_cmds = extra_cmds
        self.tasks = tasks or []
        self.shortcuts = shortcuts or []
        self.download_assets = download_assets or []
        self.cwd = get_valid_cwd()
        self.work_dir = get_work_dir(self.name)
        self.venv_dir = os.path.join(self.work_dir, VENV_DIRNAME)
        self.venv_bin_dir = os.path.join(self.venv_dir, VENV_BIN_DIRNAME)
        self.pip_path = os.path.join(self.venv_bin_dir, VENV_PIP_PATH)
        self.py_path = os.path.join(self.venv_bin_dir, VENV_PY_PATH)
        self.svc_py_path = os.path.join(self.venv_bin_dir, VENV_SVC_PY_PATH)
        self._setup()

    def _run_venv_cmds(self, cmds):
        for cmd in cmds:
            venv_cmd = [self.py_path, '-m'] + cmd
            print(f'running: {" ".join(venv_cmd)}')
            subprocess.check_call(venv_cmd)

    def _setup_venv(self):
        requires_init = not os.path.exists(self.pip_path)
        if requires_init:
            subprocess.check_call([sys.executable, '-m', 'venv', self.venv_dir])   # requires python3-venv
            print(f'created virtualenv: {self.venv_dir}')
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
        for filename, url in self.download_assets:
            file = os.path.join(self.cwd, filename)
            if not os.path.exists(file):
                urllib.request.urlretrieve(url, file)
                print(f'created asset: {file}')

    def _create_windows_shortcut(self, target_path, shortcut_path, arguments='', working_dir='', description=''):
        vbs_content = f"""Set objShell = WScript.CreateObject("WScript.Shell")
Set objShortcut = objShell.CreateShortcut("{shortcut_path}")
objShortcut.TargetPath = "{target_path}"
objShortcut.Arguments = "{arguments}"
objShortcut.WorkingDirectory = "{working_dir or os.path.dirname(target_path)}"
objShortcut.Description = "{description}"
objShortcut.Save
"""
        temp_file = os.path.join(self.cwd, 'temp.vbs')
        with open(temp_file, 'w') as fd:
            fd.write(vbs_content)
        try:
            os.system(f'cscript //NoLogo "{temp_file}"')
        finally:
            os.remove(temp_file)

    def _create_linux_shortcut(self, name, cmd, shortcut_path, description=''):
        os.makedirs(os.path.dirname(shortcut_path), exist_ok=True)
        content = f"""[Desktop Entry]
Type=Application
Name={name}
Exec={cmd}
Terminal=true
Comment={description}
"""
        with open(shortcut_path, 'w') as fd:
            fd.write(content)
        subprocess.check_call(['chmod', '+x', shortcut_path])

    def _setup_shortcut(self, name, args, headless=True):
        py_path = self.svc_py_path if headless else self.py_path
        args_str = f'-m {" ".join(args)}'
        if sys.platform == 'win32':
            file = os.path.join(APP_DIR, f'{name}.lnk')
            self._create_windows_shortcut(
                target_path=py_path,
                shortcut_path=file,
                arguments=args_str,
                working_dir=self.work_dir,
                description=name,
            )
        else:
            file = os.path.join(APP_DIR, f'{name}.desktop')
            self._create_linux_shortcut(
                name=name,
                cmd=f'{py_path} {args_str}',
                shortcut_path=file,
                description=name,
            )
        print(f'created shortcut: {file}')

    def _generate_crontab_schedule(self, schedule_minutes):
        match schedule_minutes:
            case _ if schedule_minutes < 2:
                return '* * * * *'
            case _ if schedule_minutes < 60:
                return f'*/{schedule_minutes} * * * *'
            case _ if schedule_minutes < 60 * 24:
                hours = schedule_minutes // 60
                return '0 * * * *' if hours == 1 else f'0 */{hours} * * *'
            case _:
                return '0 0 * * *'

    def _setup_linux_crontab(self, cmd, name, schedule_minutes):
        res = subprocess.run(['crontab', '-l'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        current_crontab = res.stdout if res.returncode == 0 else ''
        new_job = f'{self._generate_crontab_schedule(schedule_minutes)} flock -n /tmp/{name}.lock {cmd}\n'
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
        res = subprocess.run(['crontab', '-'], input=updated_crontab, text=True)
        if res.returncode != 0:
            raise SystemExit('Error: failed to update crontab')
        print(f'created crontab job:\n{new_job.strip()}')

    def _setup_windows_task(self, cmd, task_name, schedule_minutes):
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            raise SystemExit('Error: must run as admin to update scheduled tasks')
        subprocess.check_call([
            'schtasks', '/create',
            '/tn', task_name,
            '/tr', cmd,
            '/sc', 'minute',
            '/mo', str(schedule_minutes),
            '/rl', 'highest',
            '/f',
        ])
        print(f'created scheduled task {task_name} with cmd:\n{cmd}')

    def _setup_task(self, name, args, schedule_minutes=2):
        cmd = ' '.join([self.svc_py_path, '-m'] + args)
        if sys.platform == 'win32':
            self._setup_windows_task(cmd=cmd, task_name=name, schedule_minutes=schedule_minutes)
        else:
            self._setup_linux_crontab(cmd=cmd, name=name, schedule_minutes=schedule_minutes)

    def _setup(self):
        self._setup_venv()
        self._download_assets()
        for kwargs in self.shortcuts:
            self._setup_shortcut(**kwargs)
        for kwargs in self.tasks:
            self._setup_task(**kwargs)

    # def _get_cmd(self):
    #     if not self.cmd_args:
    #         raise SystemExit('Error: missing cmd_args')
    #     return [self.svc_py_path, '-m'] + self.cmd_args

    # def setup_shortcut(self):
    #     cmd = self._get_cmd()
    #     if sys.platform == 'win32':
    #         file = os.path.join(APP_DIR, f'{self.name}.lnk')
    #         self._create_windows_shortcut(
    #             target_path=cmd[0],
    #             shortcut_path=file,
    #             arguments=' '.join(cmd[1:]),
    #             working_dir=self.cwd,
    #             description=self.name,
    #         )
    #     else:
    #         file = os.path.join(APP_DIR, f'{self.name}.desktop')
    #         self._create_linux_shortcut(
    #             name=self.name,
    #             cmd=' '.join(cmd),
    #             shortcut_path=file,
    #             description=self.name,
    #         )
    #     print(f'created shortcut: {file}')

    # def setup_task(self):
    #     cmd = ' '.join(self._get_cmd())
    #     if sys.platform == 'win32':
    #         self._setup_windows_task(cmd=cmd, task_name=self.name)
    #     else:
    #         self._setup_linux_crontab(cmd=cmd)
