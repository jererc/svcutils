import ctypes
import os
import subprocess
import tempfile


VENV_BIN_DIRNAME = {'nt': 'Scripts', 'posix': 'bin'}[os.name]
VENV_PIP_PATH = {'nt': 'pip.exe', 'posix': 'pip'}[os.name]
VENV_PY_PATH = {'nt': 'python.exe', 'posix': 'python'}[os.name]
VENV_SVC_PY_PATH = {'nt': 'pythonw.exe', 'posix': 'python'}[os.name]


class Bootstrapper:
    def __init__(self, name, cmd_args=None, install_requires=None,
                 force_reinstall=False, venv_dirname='venv', extra_cmds=None,
                 schedule_minutes=2):
        self.name = name
        self.cmd_args = cmd_args
        self.install_requires = install_requires
        self.force_reinstall = force_reinstall
        self.venv_dirname = venv_dirname
        self.extra_cmds = extra_cmds
        self.schedule_minutes = schedule_minutes
        self.root_venv_dir = os.path.join(os.path.expanduser('~'),
            self.venv_dirname)
        self.venv_dir = os.path.join(self.root_venv_dir, self.name)
        self.venv_bin_dir = os.path.join(self.venv_dir, VENV_BIN_DIRNAME)
        self.pip_path = os.path.join(self.venv_bin_dir, VENV_PIP_PATH)
        self.py_path = os.path.join(self.venv_bin_dir, VENV_PY_PATH)
        self.svc_py_path = os.path.join(self.venv_bin_dir, VENV_SVC_PY_PATH)
        self.script_dir = os.path.join(os.path.expanduser('~'),
            f'.{self.name}')

    def setup_venv(self):
        if not os.path.exists(self.root_venv_dir):
            os.makedirs(self.root_venv_dir)
        if not os.path.exists(self.svc_py_path):
            if os.name == 'nt':   # requires python3-virtualenv on linux
                subprocess.check_call(['pip', 'install', 'virtualenv'])
            subprocess.check_call(['virtualenv', self.venv_dir])
        if self.install_requires:
            base_cmd = [self.pip_path, 'install']
            if self.force_reinstall:
                base_cmd.append('--force-reinstall')
            subprocess.check_call(base_cmd + self.install_requires)
        print(f'created the virtualenv {self.venv_dir}')
        if self.extra_cmds:
            for extra_cmd in self.extra_cmds:
                cmd = [self.py_path, '-m'] + extra_cmd
                print(f'running {" ".join(cmd)}')
                subprocess.check_call(cmd)

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

    def _create_sh_script(self, cmd):
        file = os.path.join(os.getcwd(), f'{self.name}.sh')
        with open(file, 'w') as fd:
            fd.write(f"""#!/bin/bash
{cmd}
""")
        return file

    def _create_bat_script(self, cmd):
        file = os.path.join(os.getcwd(), f'{self.name}.bat')
        with open(file, 'w') as fd:
            fd.write(f"""@echo off
{cmd}
""")
        return file

    def _create_shortcut(self, target_path, shortcut_path, arguments='',
            working_dir='', description=''):
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

    def setup_script(self):
        self.setup_venv()
        cmd = self._get_cmd()
        if os.name == 'nt':
            file = self._create_shortcut(target_path=cmd[0],
                shortcut_path=os.path.join(os.path.expanduser('~'),
                    'Desktop', f'{self.name}.lnk'),
                arguments=' '.join(cmd[1:]),
                working_dir=os.getcwd(),
                description=self.name,
            )
        else:
            file = self._create_sh_script(cmd=' '.join(cmd))
        print(f'created script {file}')

    def setup_task(self):
        self.setup_venv()
        cmd = ' '.join(self._get_cmd())
        if os.name == 'nt':
            self._setup_windows_task(cmd=cmd, task_name=self.name)
        else:
            self._setup_linux_task(cmd=cmd)
