import logging
import os
import shutil
import unittest

from svcutils import bootstrap as module


# TEST_DIR = '_test_svcutils'
# WORK_PATH = os.path.join(os.path.expanduser('~'), TEST_DIR)


# def remove_path(path):
#     if os.path.isdir(path):
#         shutil.rmtree(path)
#     elif os.path.isfile(path):
#         os.remove(path)


# def makedirs(x):
#     if not os.path.exists(x):
#         os.makedirs(x)


# class BootstrapTestCase(unittest.TestCase):
#     def setUp(self):
#         remove_path(WORK_PATH)
#         makedirs(WORK_PATH)

#     def test_1(self):
#         module.Bootstrapper(
#             script_path=os.path.realpath(__file__),
#             linux_args=['save', '--task'],
#             windows_args=['save', '--task'],
#         ).run()
