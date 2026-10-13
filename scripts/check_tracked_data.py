"""Reject runtime databases and dumps in the Git index without reading contents."""
from pathlib import PurePosixPath
import subprocess
import sys

paths = subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\0')
blocked = [name for name in paths if name and (
    PurePosixPath(name).parts[0] in {'database', 'backups'}
    or PurePosixPath(name).suffix.lower() in {'.db', '.sqlite', '.sqlite3', '.sql'}
)]
if blocked:
    print('Runtime data must not be tracked:', *blocked, sep='\n')
    sys.exit(1)
print('No tracked runtime databases or dumps.')
