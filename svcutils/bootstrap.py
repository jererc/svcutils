import ctypes
import os
import subprocess
import urllib.request


class Bootstrapper:
    def __init__(self, name, target_url, target_dir, target_args=None,
                 requires=None, force_reinstall=False, venv_dir='venv',
                 schedule_mins=2):
        self.name = name
        self.target_url = target_url
        self.target_dir = target_dir
        self.target_args = target_args
        self.requires = requires
        self.force_reinstall = force_reinstall
        self.venv_dir = venv_dir
        self.schedule_mins = schedule_mins
        self.root_venv_path = os.path.join(os.path.expanduser('~'),
            self.venv_dir)
        self.venv_path = os.path.join(self.root_venv_path, self.name)
        self.pip_path = {
            'nt': os.path.join(self.venv_path, r'Scripts\pip.exe'),
            'posix': os.path.join(self.venv_path, 'bin/pip'),
        }[os.name]
        self.svc_py_path = {
            'nt': os.path.join(self.venv_path, r'Scripts\pythonw.exe'),
            'posix': os.path.join(self.venv_path, 'bin/python'),
        }[os.name]

    def _setup_venv(self):
        if not os.path.exists(self.root_venv_path):
            os.makedirs(self.root_venv_path)
        if not os.path.exists(self.svc_py_path):
            if os.name == 'nt':   # requires python3-virtualenv on linux
                subprocess.check_call(['pip', 'install', 'virtualenv'])
            subprocess.check_call(['virtualenv', self.venv_path])
        if self.requires:
            base_cmd = [self.pip_path, 'install']
            if self.force_reinstall:
                base_cmd.append('--force-reinstall')
            subprocess.check_call(base_cmd + self.requires)
        print(f'created the virtualenv {self.venv_path}')

    def _get_target_file(self):
        print(f'downloading {self.target_url}')
        content = urllib.request.urlopen(
            self.target_url).read().decode('utf-8')
        file = os.path.join(os.path.realpath(self.target_dir),
            os.path.basename(self.target_url))
        if os.path.exists(file):
            with open(file, 'r', encoding='utf-8') as fd:
                file_content = fd.read()
        else:
            file_content = None
        if content != file_content:
            with open(file, 'w', encoding='utf-8') as fd:
                fd.write(content)
            print(f'updated target {file}')
        return file

    def _get_cmd(self):
        target_file = self._get_target_file()
        args_str = f' {" ".join(self.target_args)}' if self.target_args else ''
        return f'{self.svc_py_path} {target_file}{args_str}'

    def _generate_crontab_schedule(self):
        match self.schedule_mins:
            case _ if self.schedule_mins < 2:
                return '* * * * *'
            case _ if self.schedule_mins < 60:
                return f'*/{self.schedule_mins} * * * *'
            case _ if self.schedule_mins < 60 * 24:
                hours = self.schedule_mins // 60
                if hours == 1:
                    return '0 * * * *'
                return f'0 */{hours} * * *'
            case _:
                return '0 0 * * *'

    def _setup_linux_task(self, cmd):
        res = subprocess.run(['crontab', '-l'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        current_crontab = res.stdout if res.returncode == 0 else ''
        new_job = f'{self._generate_crontab_schedule()} {cmd}\n'
        updated_crontab = ''
        job_found = False
        for line in current_crontab.splitlines():
            if cmd in line:
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
        print('successfully updated crontab')

    def _setup_windows_task(self, cmd, task_name):
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            raise SystemExit('must run as admin to update scheduled tasks')
        subprocess.check_call(['schtasks', '/create',
            '/tn', task_name,
            '/tr', cmd,
            '/sc', 'minute',
            '/mo', str(self.schedule_mins),
            '/rl', 'highest',
            '/f',
        ])
        subprocess.check_call(['schtasks', '/run',
            '/tn', task_name])

    def run(self):
        self._setup_venv()
        if self.schedule_mins is not None:
            cmd = self._get_cmd()
            if os.name == 'nt':
                self._setup_windows_task(cmd=cmd, task_name=self.name)
            else:
                self._setup_linux_task(cmd=cmd)


class Bootstrap:
    def __init__(self, name, script_module, script_args=None,
                 install_requires=None, force_reinstall=False,
                 venv_dir='venv', schedule_mins=2):
        self.name = name
        self.script_module = script_module
        self.script_args = script_args or []
        self.install_requires = install_requires
        self.force_reinstall = force_reinstall
        self.venv_dir = venv_dir
        self.schedule_mins = schedule_mins
        self.root_venv_path = os.path.join(os.path.expanduser('~'),
            self.venv_dir)
        self.venv_path = os.path.join(self.root_venv_path, self.name)
        self.venv_bin_path = {
            'nt': os.path.join(self.venv_path, 'Scripts'),
            'posix': os.path.join(self.venv_path, 'bin'),
        }[os.name]
        self.pip_path = {
            'nt': os.path.join(self.venv_bin_path, 'pip.exe'),
            'posix': os.path.join(self.venv_bin_path, 'pip'),
        }[os.name]
        self.svc_py_path = {
            'nt': os.path.join(self.venv_bin_path, 'pythonw.exe'),
            'posix': os.path.join(self.venv_bin_path, 'python'),
        }[os.name]

    def _setup_venv(self):
        if not os.path.exists(self.root_venv_path):
            os.makedirs(self.root_venv_path)
        if not os.path.exists(self.svc_py_path):
            if os.name == 'nt':   # requires python3-virtualenv on linux
                subprocess.check_call(['pip', 'install', 'virtualenv'])
            subprocess.check_call(['virtualenv', self.venv_path])
        if self.install_requires:
            base_cmd = [self.pip_path, 'install']
            if self.force_reinstall:
                base_cmd.append('--force-reinstall')
            subprocess.check_call(base_cmd + self.install_requires)
        print(f'created the virtualenv {self.venv_path}')

    # def _get_cmd(self):
    #     script = os.path.join(self.venv_bin_path, self.name)
    #     args = f' {" ".join(self.script_args)}' if self.script_args else ''
    #     return f'{script}{args}'

    def _get_cmd(self):
        args = ['-m', self.script_module] + (self.script_args or [])
        return f'{self.svc_py_path} {" ".join(args)}'

    def _generate_crontab_schedule(self):
        match self.schedule_mins:
            case _ if self.schedule_mins < 2:
                return '* * * * *'
            case _ if self.schedule_mins < 60:
                return f'*/{self.schedule_mins} * * * *'
            case _ if self.schedule_mins < 60 * 24:
                hours = self.schedule_mins // 60
                if hours == 1:
                    return '0 * * * *'
                return f'0 */{hours} * * *'
            case _:
                return '0 0 * * *'

    def _setup_linux_task(self, cmd):
        res = subprocess.run(['crontab', '-l'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        current_crontab = res.stdout if res.returncode == 0 else ''
        new_job = f'{self._generate_crontab_schedule()} {cmd}\n'
        updated_crontab = ''
        job_found = False
        for line in current_crontab.splitlines():
            if cmd in line:
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
        print('successfully updated crontab')

    def _setup_windows_task(self, cmd, task_name):
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            raise SystemExit('must run as admin to update scheduled tasks')
        subprocess.check_call(['schtasks', '/create',
            '/tn', task_name,
            '/tr', cmd,
            '/sc', 'minute',
            '/mo', str(self.schedule_mins),
            '/rl', 'highest',
            '/f',
        ])
        subprocess.check_call(['schtasks', '/run',
            '/tn', task_name])

    def run(self):
        self._setup_venv()
        if self.schedule_mins is not None:
            cmd = self._get_cmd()
            print(f'cmd: {cmd}')
            if os.name == 'nt':
                self._setup_windows_task(cmd=cmd, task_name=self.name)
            else:
                self._setup_linux_task(cmd=cmd)
