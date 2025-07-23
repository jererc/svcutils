import logging
import os

WORK_DIR = os.path.expanduser('~/tmp/tests/svcutils')
os.makedirs(WORK_DIR, exist_ok=True)
import svcutils as module
logging.getLogger('').handlers.clear()
