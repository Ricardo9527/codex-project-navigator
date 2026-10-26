"""Read Codex rollouts in place, including sessions compacted to .jsonl.zst."""
from contextlib import contextmanager
from pathlib import Path
import shutil
import subprocess
import tempfile

try:
    from compression import zstd
except ImportError:
    zstd = None


def session_path(path):
    path = Path(path)
    compressed = Path(str(path) + '.zst')
    return compressed if not path.is_file() and compressed.is_file() else path


@contextmanager
def open_session(path):
    path = session_path(path)
    if path.suffix != '.zst':
        with path.open(encoding='utf-8') as stream:
            yield stream
    elif zstd is not None:
        try:
            with zstd.open(path, 'rt', encoding='utf-8') as stream:
                yield stream
        except zstd.ZstdError as error:
            raise ValueError(f'无法读取压缩会话 {path}：{error}') from error
    else:
        command = shutil.which('zstd')
        if command is None:
            raise ValueError(f'读取压缩会话需要 Python 3.14+ 的 compression.zstd 或 zstd 命令：{path}')
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([command, '-dc', '--', str(path)], stdout=subprocess.PIPE,
                                       stderr=errors, text=True, encoding='utf-8')
            try:
                with process.stdout as stream:
                    yield stream
                    if process.wait():
                        errors.seek(0)
                        raise ValueError(f'无法读取压缩会话 {path}：{errors.read().decode("utf-8", errors="replace").strip()}')
            finally:
                if process.poll() is None:
                    process.terminate()
                process.wait()
