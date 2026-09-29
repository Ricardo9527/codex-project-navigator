import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from project_records import record_path
from content_pages import read_page, read_resource, resource_action


class ContentPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'data'
        self.project_root = self.root / 'project'
        self.project_root.mkdir()
        self.project = {'id': 'sample', 'name': '字幕项目', 'path': str(self.project_root)}
        self.subtitle = self.project_root / '交付.srt'
        self.subtitle.write_text('1\n00:00:01,000 --> 00:00:02,000\n测试字幕\n')
        self.page = {'version': 1, 'projectId': 'sample', 'cards': [
            {'id': 'delivery', 'resources': [{'id': 'subtitle', 'path': '交付.srt'}]}]}
        self.args = {'cardId': 'delivery', 'resourceId': 'subtitle'}
        self.save()

    def save(self):
        path = record_path(self.project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.page))

    def tearDown(self):
        self.temp.cleanup()

    def test_registered_subtitle_preview_is_read_only_and_reveal_uses_record(self):
        before = self.subtitle.read_bytes()
        page_before = record_path(self.project).read_bytes()
        result = resource_action(self.data, self.project, 'pagePreview', self.args)
        self.assertEqual(result['type'], 'text')
        self.assertIn('测试字幕', result['text'])
        self.assertFalse(result['truncated'])
        with patch('content_pages.subprocess.run') as run:
            resource_action(self.data, self.project, 'pageReveal', {**self.args, 'path': '/private/other'})
            run.assert_called_once_with(['open', '-R', str(self.subtitle.resolve())], check=True)
        self.assertEqual(self.subtitle.read_bytes(), before)
        self.assertEqual(record_path(self.project).read_bytes(), page_before)

    def test_project_boundary_and_unknown_resource(self):
        with self.assertRaisesRegex(ValueError, '找不到'):
            read_resource(self.data, self.project, {'cardId': 'delivery', 'resourceId': '../other'})
        outside = self.root / 'outside.txt'
        outside.write_text('outside')
        self.subtitle.unlink()
        self.subtitle.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, '超出'):
            resource_action(self.data, self.project, 'pagePreview', self.args)

    def test_missing_file_keeps_page_but_preview_reports_error(self):
        self.subtitle.unlink()
        self.assertFalse(read_page(self.data, self.project)['cards'][0]['resources'][0]['exists'])
        with self.assertRaisesRegex(ValueError, '移动或删除'):
            read_resource(self.data, self.project, self.args)

    def test_no_page_and_incorrect_project_do_not_supply_other_content(self):
        self.assertIsNone(read_page(self.data, {'id': 'other', 'path': str(self.root/'other-project')}))
        self.page['projectId'] = 'other'
        self.save()
        with self.assertRaisesRegex(ValueError, '归属'):
            read_page(self.data, self.project)

    def test_explicit_global_skill_entry_and_boundary(self):
        skill_root = self.root/'.codex/skills/example'
        skill_root.mkdir(parents=True)
        (skill_root/'SKILL.md').write_text('# Example skill')
        self.page['cards'][0]['resources'] = [{'id':'subtitle','source':'skill','path':'example/SKILL.md'}]
        self.save()
        with patch('content_pages.Path.home', return_value=self.root):
            result = resource_action(self.data, self.project, 'pagePreview', self.args)
            self.assertIn('Example skill', result['text'])
            self.page['cards'][0]['resources'][0]['path'] = '../../secrets/key.env'
            self.save()
            with self.assertRaises(ValueError):
                read_resource(self.data, self.project, self.args)

    def test_installed_skill_symlink_is_a_valid_manifest_entry(self):
        installed=self.root/'.codex/skills';installed.mkdir(parents=True)
        source=self.root/'skill-source';source.mkdir();(source/'SKILL.md').write_text('# Installed skill')
        (installed/'example').symlink_to(source,target_is_directory=True)
        self.page['cards'][0]['resources']=[{'id':'subtitle','source':'skill','path':'example/SKILL.md'}];self.save()
        with patch('content_pages.Path.home',return_value=self.root):
            self.assertIn('Installed skill',resource_action(self.data,self.project,'pagePreview',self.args)['text'])



if __name__ == '__main__':
    unittest.main()
