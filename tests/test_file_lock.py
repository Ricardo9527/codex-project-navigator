import tempfile
import types
import unittest
from unittest.mock import patch,Mock
from file_lock import lock_exclusive

class FileLockTests(unittest.TestCase):
    def test_windows_locks_one_real_byte_from_start(self):
        native=types.SimpleNamespace(LK_LOCK=1,locking=Mock())
        with tempfile.TemporaryFile(mode='w+') as stream:
            with patch('file_lock.sys.platform','win32'),patch.dict('sys.modules',{'msvcrt':native}):
                lock_exclusive(stream)
            native.locking.assert_called_once_with(stream.fileno(),1,1)
            stream.seek(0);self.assertEqual(stream.read(),'0')
