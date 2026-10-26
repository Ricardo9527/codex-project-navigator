import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
import test_library
import conversation_assets
import maintenance
from session_files import open_session


class CompressedSessionTests(unittest.TestCase):
    setUp = test_library.LibraryTests.setUp
    tearDown = test_library.LibraryTests.tearDown
    write_messages = test_library.LibraryTests.write_messages
    def compress(self):
        target=Path(str(self.rollout)+'.zst')
        subprocess.run(['zstd','-q','-f',str(self.rollout),'-o',str(target)],check=True)
        self.rollout.unlink()
        return target

    def test_compacted_session_indexes_text_deliveries_and_lifecycle(self):
        with self.rollout.open('a') as stream:
            stream.write(json.dumps({'type':'event_msg','payload':{'type':'task_completed'}})+'\n')
        target=self.compress();before=target.read_bytes()
        self.assertEqual(self.hub.scan()['errors'],[])
        self.assertEqual(self.hub.detail({'projectId':'a','query':'四元数'})['totalThreads'],1)
        self.assertEqual(conversation_assets.thread_assets(self.hub,'t')[0]['path'],str(self.file))
        self.assertEqual(maintenance.native_state(self.hub,'t'),'finished')
        with patch('session_files.zstd',None):
            self.assertIn('四元数',self.hub.messages(self.rollout))
        self.assertEqual(target.read_bytes(),before)
        self.assertFalse(self.rollout.exists())

    def test_plain_file_preferred_and_real_missing_or_corrupt_stays_an_error(self):
        target=self.compress();target.write_bytes(b'not-zstd')
        with self.assertRaisesRegex(ValueError,'压缩会话'):
            self.hub.messages(self.rollout)
        self.write_messages('当前原文优先')
        self.assertIn('当前原文优先',self.hub.messages(self.rollout))
        target.unlink();self.rollout.unlink()
        with self.assertRaises(FileNotFoundError):
            with open_session(self.rollout) as stream:stream.read()

