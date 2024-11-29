import ctypes
import os
import subprocess


VENV_BIN_DIRNAME = {'nt': 'Scripts', 'posix': 'bin'}[os.name]
VENV_PIP_PATH = {'nt': 'pip.exe', 'posix': 'pip'}[os.name]
VENV_SVC_PY_PATH = {'nt': 'pythonw.exe', 'posix': 'python'}[os.name]


class Bootstrapper:
    def __init__(self, name, cmd_args=None, install_requires=None,
                 force_reinstall=False, venv_dir='venv', extra_cmds=None,
                 schedule_minutes=2):
        self.name = name
        self.cmd_args = cmd_args
        self.install_requires = install_requires
        self.force_reinstall = force_reinstall
        self.venv_dir = venv_dir
        self.extra_cmds = extra_cmds
        self.schedule_minutes = schedule_minutes
        self.root_venv_path = os.path.join(os.path.expanduser('~'),
            self.venv_dir)
        self.venv_path = os.path.join(self.root_venv_path, self.name)
        self.venv_bin_path = os.path.join(self.venv_path, VENV_BIN_DIRNAME)
        self.pip_path = os.path.join(self.venv_bin_path, VENV_PIP_PATH)
        self.svc_py_path = os.path.join(self.venv_bin_path, VENV_SVC_PY_PATH)

    def setup_venv(self):
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
        if self.extra_cmds:
            for extra_cmd in self.extra_cmds:
                cmd = [self.svc_py_path, '-m'] + extra_cmd
                print(f'running {" ".join(cmd)}')
                subprocess.check_call(cmd)

    def _get_cmd(self):
        if not self.cmd_args:
            raise SystemExit('missing cmd_args')
        args = ['-m'] + self.cmd_args
        return f'{self.svc_py_path} {" ".join(args)}'

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
        subprocess.check_call(['schtasks', '/run',
            '/tn', task_name])
        print(f'created the task {task_name}')

    def _setup_windows_script(self, cmd):
        file = os.path.join(os.getcwd(), f'{self.name}.bat')
        with open(file, 'w') as fd:
            fd.write(f"""@echo off
{cmd}
""")
        print(f'created the script {file}')

    def _setup_linux_script(self, cmd):
        file = os.path.join(os.getcwd(), f'{self.name}.sh')
        with open(file, 'w') as fd:
            fd.write(f"""#!/bin/bash
{cmd}
""")
        print(f'created the script {file}')

    def setup_task(self):
        cmd = self._get_cmd()
        print(f'cmd: {cmd}')
        print(f'schedule recurrence: {self.schedule_minutes} minutes')
        self.setup_venv()
        if os.name == 'nt':
            self._setup_windows_task(cmd=cmd, task_name=self.name)
        else:
            self._setup_linux_task(cmd=cmd)

    def setup_script(self):
        cmd = self._get_cmd()
        print(f'cmd: {cmd}')
        self.setup_venv()
        if os.name == 'nt':
            self._setup_windows_script(cmd=cmd)
        else:
            self._setup_linux_script(cmd=cmd)
