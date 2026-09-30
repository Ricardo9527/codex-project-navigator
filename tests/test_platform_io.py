import unittest
from unittest.mock import patch
from pathlib import Path
import platform_io


class PlatformIOTests(unittest.TestCase):
    def test_windows_opens_protocol_without_shell_interpolation(self):
        with patch.object(platform_io.sys, 'platform', 'win32'), patch.object(platform_io.os, 'startfile', create=True) as start:
            platform_io.open_url('codex://threads/a')
            start.assert_called_once_with('codex://threads/a')

    def test_linux_reveals_parent_directory_as_one_argument(self):
        with patch.object(platform_io.sys, 'platform', 'linux'), patch.object(platform_io.subprocess, 'run') as run:
            platform_io.reveal(Path('/tmp/project with spaces/file.txt'))
            run.assert_called_once_with(['xdg-open', '/tmp/project with spaces'], check=True)
