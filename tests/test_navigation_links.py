import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse

from library import Library
from navigation_links import navigation_url


class NavigationLinkTests(unittest.TestCase):
    def test_public_plugin_link_preserves_project_identity(self):
        value = urlparse(navigation_url('project / 中文'))
        self.assertEqual(value.scheme, 'codex')
        self.assertEqual(value.path, '/project-navigator@project-navigation-local/app/browse_navigation')
        path = parse_qs(value.query)['path'][0]
        self.assertEqual(unquote(path.removeprefix('/projects/')), 'project / 中文')

    def test_project_row_uses_registered_alias_before_opening(self):
        hub = object.__new__(Library)
        hub.aliases = {'native': 'registered'}
        project = {'id': 'registered', 'name': 'Project', 'path': '/project'}
        with patch.object(hub, 'refresh_projects'), patch.object(hub, 'project', return_value=project) as resolve, patch('library.subprocess.run') as run:
            result = hub.dispatch('openNavigation', {'projectId': 'native'})
        resolve.assert_called_once_with('registered')
        run.assert_called_once_with(['/usr/bin/open', result['url']], check=True)
        target=urlparse(parse_qs(urlparse(result['url']).query)['path'][0])
        self.assertEqual(target.path, '/projects/registered')
        self.assertTrue(parse_qs(target.query)['entry'][0])
        self.assertEqual(result['projectId'], 'registered')
