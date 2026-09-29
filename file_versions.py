"""Content identity for explicitly registered project results."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path


def stamp(path):
    path=Path(path)
    if not path.exists():return None
    if path.is_file():
        s=path.stat();return [s.st_size,s.st_mtime_ns,s.st_ino]
    return [[str(p.relative_to(path)),p.stat().st_size,p.stat().st_mtime_ns] for p in sorted(path.rglob('*')) if p.is_file() and not p.is_symlink()]


def version_stamp(path):
    """Opaque wire identity; nanosecond integers cannot round-trip through JS Numbers."""
    value=stamp(path)
    return hashlib.sha256(json.dumps(value).encode()).hexdigest() if value is not None else None


@lru_cache(maxsize=256)
def _file_digest(path, identity):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def fingerprint(path):
    path=Path(path)
    if not path.exists():return None
    if path.is_file():return 'sha256:'+_file_digest(str(path),tuple(stamp(path)))
    digest=hashlib.sha256()
    for p in sorted(path.rglob('*')):
        if p.is_symlink():raise ValueError('成果包包含符号链接，需先明确文件版本边界。')
        if p.is_file():digest.update((str(p.relative_to(path))+'\0'+fingerprint(p)+'\n').encode())
    return 'sha256:'+digest.hexdigest()
