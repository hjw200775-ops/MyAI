import os
import runpy
import socket
import sys
import tempfile
from pathlib import Path

def forbidden(*args, **kwargs):
    raise AssertionError('Network disabled during offline tests')

socket.socket.connect = forbidden
socket.create_connection = forbidden
os.environ['MYAI_LOAD_DOTENV'] = '0'
with tempfile.TemporaryDirectory() as folder:
    os.environ['MYAI_DB_PATH'] = str(Path(folder) / 'memory.db')
    os.environ['MYAI_DATA_DIR'] = str(Path(folder) / 'data')
    os.environ['MYAI_SETTINGS_PATH'] = str(Path(folder) / 'settings.json')
    target = sys.argv[1]
    sys.argv = [target]
    runpy.run_path(target, run_name='__main__')
