from setuptools import setup, find_packages

setup(
    name='svcutils',
    version='2026.02.18.120725',
    author='jererc',
    author_email='jererc@gmail.com',
    url='https://github.com/jererc/svcutils',
    packages=find_packages(exclude=['tests*']),
    python_requires='>=3.10',
    install_requires=[
        'psutil',
        'requests',
    ],
    extras_require={
        'dev': ['flake8', 'pytest'],
        ':sys_platform == "linux"': [
            'ewmh',
        ],
        ':sys_platform == "win32"': [
            'pywin32',
            'win11toast',
        ],
    },
    include_package_data=True,
)
