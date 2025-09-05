from setuptools import setup, find_packages

setup(
    name='svcutils',
    version='2025.09.05.151715',
    author='jererc',
    author_email='jererc@gmail.com',
    url='https://github.com/jererc/svcutils',
    packages=find_packages(exclude=['tests*']),
    python_requires='>=3.10',
    install_requires=[
        'psutil',
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
