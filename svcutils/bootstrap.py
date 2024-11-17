import ctypes
import os
import subprocess


class Bootstrapper:
    def __init__(self, name, target_path, requires=None, force_reinstall=False,
                 venv_dir='venv', schedule_mins=2, args=None):
        self.name = name
        self.target_path = os.path.realpath(target_path)
        if not os.path.exists(self.target_path):
            raise Exception(f'target not found: {target_path}')
        self.requires = requires
        self.force_reinstall = force_reinstall
        self.venv_dir = venv_dir
        self.schedule_mins = schedule_mins
        self.args = args
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
        print(f'Created the virtualenv in {self.venv_path}')

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
            raise SystemExit('Failed to update crontab')
        print('Successfully updated crontab')

    def _setup_windows_task(self, cmd, task_name):
        if ctypes.windll.shell32.IsUserAnAdmin() == 0:
            raise SystemExit('Failed: must run as admin')
        try:
            subprocess.check_call(['schtasks', '/end',
                '/tn', task_name,
                '/f',
            ])
            subprocess.check_call(['schtasks', '/delete',
                '/tn', task_name,
                '/f',
            ])
        except subprocess.CalledProcessError:
            pass
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

    def _get_cmd(self):
        args_str = f' {" ".join(self.args)}' if self.args else ''
        return f'{self.svc_py_path} {self.target_path}{args_str}'

    def run(self):
        self._setup_venv()
        if self.schedule_mins is not None:
            cmd = self._get_cmd()
            if os.name == 'nt':
                self._setup_windows_task(cmd=cmd, task_name=self.name)
            else:
                self._setup_linux_task(cmd=cmd)
