"""Small OS boundary for explicit desktop file and URL actions."""
import os
from pathlib import Path
import subprocess
import sys


def open_url(url):
    if sys.platform == 'darwin':
        subprocess.run(['/usr/bin/open', url], check=True)
    elif sys.platform == 'win32':
        os.startfile(url)
    else:
        subprocess.run(['xdg-open', url], check=True)


def reveal(path):
    path = Path(path)
    if sys.platform == 'darwin':
        subprocess.run(['open', '-R', str(path)], check=True)
    elif sys.platform == 'win32':
        subprocess.run(['explorer.exe', '/select,', str(path)], check=True)
    else:
        open_url(str(path.parent))


def choose_file():
    if sys.platform == 'darwin':
        result = subprocess.run(['osascript', '-e', 'POSIX path of (choose file with prompt "选择成果文件")'], capture_output=True, text=True)
        if result.returncode:
            if '(-128)' in result.stderr:
                return None
            raise ValueError(result.stderr.strip())
        return result.stdout.strip()
    try:
        from tkinter import Tk, filedialog
    except ImportError as error:
        raise ValueError('选择文件需要 Python tkinter；也可让 Agent 用 registerResource 登记文件。') from error
    window = Tk()
    window.withdraw()
    try:
        return filedialog.askopenfilename(title='选择成果文件') or None
    finally:
        window.destroy()
