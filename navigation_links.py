"""Public desktop plugin links; project identity stays in the app-relative path."""
from urllib.parse import quote


def navigation_url(project_id=None, entry=None):
    path = '/projects/' + quote(project_id, safe='') if project_id else '/'
    if entry is not None:
        path += '?entry=' + quote(entry, safe='')
    return 'codex://plugins/project-navigator@project-navigation-local/app/browse_navigation?path=' + quote(path, safe='')
