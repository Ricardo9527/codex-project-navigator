import importlib.util
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

spec=importlib.util.spec_from_file_location('record_hook',Path(__file__).resolve().parents[1]/'scripts/project-record-hook.py')
hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)


class HookTests(unittest.TestCase):
    def test_start_only_provides_entry_and_does_not_initialize_files_or_git(self):
        with tempfile.TemporaryDirectory() as temp:
            project={'id':'p','name':'Project','path':temp}
            hub=SimpleNamespace(refresh_projects=lambda:None,owner=lambda cwd:'p',project=lambda pid:project)
            event={'cwd':temp,'session_id':'thread','hook_event_name':'SessionStart'}
            output=hook.handle(event,hub)
            self.assertIn('.project-library/record.json',output['hookSpecificOutput']['additionalContext'])
            self.assertEqual(list(Path(temp).iterdir()),[])

    def test_prompt_stop_and_interrupt_are_inert_even_with_old_caller(self):
        # No project/database lookup and no continuation on ordinary turns.
        for name in ['UserPromptSubmit','Stop','Interrupt']:
            self.assertEqual(hook.handle({'hook_event_name':name},None),{})
