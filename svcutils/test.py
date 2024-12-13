import os
from pathlib import Path
import sys


def is_relative_to(base_path, target_path):
    base = Path(base_path).resolve()
    target = Path(target_path).resolve()
    return target.is_relative_to(base)


def get_valid_cwd():
    path = os.getcwd()
    admin_dir = {
        'nt': os.environ.get('WINDIR', r'C:\Windows'),
        'posix': '/root',
    }[os.name]
    print(f'{admin_dir=}')
    if is_relative_to(admin_dir, path):
        raise ValueError(f'invalid current working dir {path}')
    return path


# print(f'{os.getcwd()=}')
# print(f'{__file__=}')
# print(f'{sys.stdin.isatty()=}')
# print(f'{sys.stdout.isatty()=}')
# print(f'{sys.argv=}')

print(f'{get_valid_cwd()=}')
