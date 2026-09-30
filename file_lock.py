"""Exclusive lock held until the caller closes the lock file."""
import os
import sys


def lock_exclusive(stream):
    if sys.platform == 'win32':
        import msvcrt
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write('0')
            stream.flush()
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
    else:
        import fcntl
        fcntl.flock(stream, fcntl.LOCK_EX)
