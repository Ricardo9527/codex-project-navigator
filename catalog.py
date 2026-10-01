"""Local project catalog. Codex's database is opened read-only; organization is ours."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import json
import mimetypes
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from platform_io import open_url, reveal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
STATES = {"candidate": "候选", "review": "待确认", "accepted": "已采用", "superseded": "历史版本"}
KINDS = {"image": "图片", "script": "剧本", "storyboard": "分镜", "prompt": "提示词", "document": "文档", "feature": "功能记录"}


class Hub:
    def __init__(self, codex_db=None, data_dir=None):
        self.codex_db = Path(codex_db or Path.home() / ".codex/state_5.sqlite")
        self.data_dir = Path(data_dir or ROOT / "data")
        self.projects_file = self.data_dir / "projects.json"
        if self.projects_file.exists():
            self.registry = json.loads(self.projects_file.read_text())
        else:
            with self.codex() as db:
                self.registry = [dict(r) for r in db.execute('SELECT p.id,p.name,r.path FROM projects p JOIN project_roots r ON p.id=r.project_id WHERE r.position=0 ORDER BY p.position')]
            if codex_db is None:
                state_path=Path.home()/'.codex/.codex-global-state.json'
                state=json.loads(state_path.read_text()) if state_path.exists() else {}
                desktops=state.get('local-projects',{})
                for project in self.registry:
                    record=Path(project['path'])/'.project-library/record.json'
                    identity=next((identity for identity,item in desktops.items() if project['path'] in item.get('rootPaths',[])),project['id'])
                    project['id']=json.loads(record.read_text())['projectId'] if record.exists() else identity
        self.roots = sorted([(str(Path(p["path"]).resolve()), p["id"]) for p in self.registry], reverse=True, key=lambda x: len(x[0]))
        self.aliases = {p['desktopId']: p['id'] for p in self.registry if p.get('desktopId')}
        with self.codex() as db:
            for row in db.execute("SELECT project_id,path FROM project_roots"):
                for root, project_id in self.roots:
                    if str(Path(row["path"]).resolve()) == root:
                        self.aliases[row["project_id"]] = project_id
        self.lock = threading.RLock()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.local() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL,
                UNIQUE(project_id, name));
            CREATE TABLE IF NOT EXISTS thread_categories (
                thread_id TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories(id),
                PRIMARY KEY(thread_id, category_id));
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
                path TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL,
                source_thread_id TEXT, note TEXT NOT NULL DEFAULT '',
                updated_at INTEGER NOT NULL DEFAULT (unixepoch()), UNIQUE(project_id, path));
            CREATE TABLE IF NOT EXISTS artifact_categories (
                artifact_id INTEGER NOT NULL REFERENCES artifacts(id),
                category_id INTEGER NOT NULL REFERENCES categories(id),
                PRIMARY KEY(artifact_id, category_id));
            """)

    @contextmanager
    def local(self):
        db = sqlite3.connect(self.data_dir / "hub.sqlite")
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def codex(self):
        db = sqlite3.connect(self.codex_db.resolve().as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        try:
            yield db
        finally:
            db.close()

    def projects(self):
        return self.registry

    def project(self, project_id):
        for project in self.projects():
            if project["id"] == project_id:
                return project
        raise ValueError("找不到这个项目。请刷新项目列表后重试。")

    def owner(self, cwd, native_id=None):
        path = os.path.realpath(cwd)
        return next((project_id for root, project_id in self.roots if path == root or path.startswith(root + os.sep)), self.aliases.get(native_id))

    def all_threads(self):
        with self.codex() as db:
            rows = db.execute("""SELECT id, COALESCE(NULLIF(name,''), title) AS title,
                cwd, updated_at, archived, git_branch, COALESCE(preview,'') AS preview, project_id
                FROM threads WHERE agent_role IS NULL AND agent_path IS NULL
                AND COALESCE(thread_source,'') NOT IN ('subagent','guardian_review')
                ORDER BY updated_at DESC""").fetchall()
        return [dict(r) for r in rows]

    def thread(self, thread_id):
        with self.codex() as db:
            row = db.execute("SELECT id,cwd,project_id,COALESCE(NULLIF(name,''),title) AS title,updated_at,archived FROM threads WHERE id=?", (thread_id,)).fetchone()
        if row is None:
            raise ValueError("该对话已不存在。")
        return dict(row)

    def overview(self, args):
        projects = self.projects()
        counts = {p["id"]: 0 for p in projects}
        for t in self.all_threads():
            owner = self.owner(t["cwd"], t["project_id"])
            if owner in counts and not t["archived"]:
                counts[owner] += 1
        with self.local() as db:
            artifacts = dict(db.execute("SELECT project_id,count(*) FROM artifacts GROUP BY project_id").fetchall())
        return {"projects": [{**p, "threads": counts[p["id"]], "artifacts": artifacts.get(p["id"], 0)} for p in projects],
                "aliases": self.aliases, "searchScope": "对话标题与已有摘要"}

    def category_ids(self, db, table, owner_column, owner_id):
        return [r[0] for r in db.execute(f"SELECT category_id FROM {table} WHERE {owner_column}=?", (owner_id,))]

    def detail(self, args):
        project = self.project(args["projectId"])
        query = args.get("query", "").strip().casefold()
        category = args.get("categoryId")
        archived = args.get("includeArchived", False)
        with self.local() as db:
            categories = [dict(r) for r in db.execute("SELECT * FROM categories WHERE project_id=? ORDER BY id", (project["id"],))]
            threads = []
            for t in self.all_threads():
                if self.owner(t["cwd"], t["project_id"]) != project["id"] or (t["archived"] and not archived):
                    continue
                ids = self.category_ids(db, "thread_categories", "thread_id", t["id"])
                if category is not None and category not in ids:
                    continue
                if query and query not in (t["title"] + " " + t["preview"]).casefold():
                    continue
                # The original title may be a pasted prompt. Keep its actual value, bounded for display.
                threads.append({**t, "title": t["title"][:300], "preview": t["preview"][:400], "categoryIds": ids})
            artifacts = []
            for row in db.execute("SELECT * FROM artifacts WHERE project_id=? ORDER BY updated_at DESC,id DESC", (project["id"],)):
                a = dict(row)
                a["categoryIds"] = self.category_ids(db, "artifact_categories", "artifact_id", a["id"])
                if category is not None and category not in a["categoryIds"]:
                    continue
                if query and query not in (a["title"] + " " + a["note"] + " " + a["path"]).casefold():
                    continue
                a["exists"] = Path(a["path"]).is_file()
                artifacts.append(a)
        offset = int(args.get("offset", 0))
        if offset < 0:
            raise ValueError("无效的页码。")
        return {"project": project, "categories": categories, "threads": threads[offset:offset + 60],
                "totalThreads": len(threads), "offset": offset, "artifacts": artifacts,
                "statuses": STATES, "kinds": KINDS}

    def add_category(self, args):
        self.project(args["projectId"])
        name = args["name"].strip()
        if not name or len(name) > 60:
            raise ValueError("分类名称需要 1–60 个字符。")
        with self.lock, self.local() as db:
            cursor = db.execute("INSERT INTO categories(project_id,name) VALUES (?,?)", (args["projectId"], name))
            return {"id": cursor.lastrowid}

    def validate_categories(self, db, project_id, ids):
        existing = {r[0] for r in db.execute("SELECT id FROM categories WHERE project_id=?", (project_id,))}
        if not isinstance(ids, list) or not set(ids) <= existing:
            raise ValueError("分类不属于当前项目。")

    def tag_thread(self, args):
        thread = self.thread(args["threadId"])
        project_id = self.owner(thread["cwd"], thread["project_id"])
        with self.lock, self.local() as db:
            self.validate_categories(db, project_id, args["categoryIds"])
            db.execute("DELETE FROM thread_categories WHERE thread_id=?", (thread["id"],))
            db.executemany("INSERT INTO thread_categories VALUES (?,?)", [(thread["id"], c) for c in set(args["categoryIds"])])
        return {"saved": True}

    def save_artifact(self, args):
        project = self.project(args["projectId"])
        path = Path(args["path"]).expanduser().resolve()
        if not path.is_relative_to(Path(project["path"]).resolve()) or not path.is_file():
            raise ValueError("请选择当前项目目录内已经存在的文件。")
        title = args["title"].strip()
        if not title or len(title) > 200:
            raise ValueError("成果名称需要 1–200 个字符。")
        if args["kind"] not in KINDS or args["status"] not in STATES:
            raise ValueError("无效的成果类型或状态。")
        source = args.get("sourceThreadId") or None
        if source and self.owner(self.thread(source)["cwd"], self.thread(source)["project_id"]) != project["id"]:
            raise ValueError("来源对话不属于当前项目。")
        with self.lock, self.local() as db:
            self.validate_categories(db, project["id"], args["categoryIds"])
            if args.get("id") is not None:
                old = db.execute("SELECT project_id FROM artifacts WHERE id=?", (args["id"],)).fetchone()
                if old is None or old[0] != project["id"]:
                    raise ValueError("该成果不属于当前项目。")
                db.execute("""UPDATE artifacts SET title=?,path=?,kind=?,status=?,source_thread_id=?,note=?,updated_at=unixepoch()
                    WHERE id=?""", (title, str(path), args["kind"], args["status"], source, args.get("note", ""), args["id"]))
                artifact_id = args["id"]
            else:
                cursor = db.execute("INSERT INTO artifacts(project_id,title,path,kind,status,source_thread_id,note) VALUES (?,?,?,?,?,?,?)",
                                    (project["id"], title, str(path), args["kind"], args["status"], source, args.get("note", "")))
                artifact_id = cursor.lastrowid
            db.execute("DELETE FROM artifact_categories WHERE artifact_id=?", (artifact_id,))
            db.executemany("INSERT INTO artifact_categories VALUES (?,?)", [(artifact_id, c) for c in set(args["categoryIds"])])
        return {"id": artifact_id}

    def artifact_file(self, args):
        with self.local() as db:
            row = db.execute("SELECT * FROM artifacts WHERE id=?", (args["id"],)).fetchone()
        if row is None:
            raise ValueError("找不到该成果。")
        path = Path(row["path"]).resolve()
        project = self.project(row["project_id"])
        if not path.is_relative_to(Path(project["path"]).resolve()):
            raise ValueError("文件已移到项目目录外。")
        if not path.is_file():
            raise ValueError("文件已移动或删除，请编辑成果记录。")
        return path

    def preview(self, args):
        path = self.artifact_file(args)
        if path.stat().st_size > 15 * 1024 * 1024:
            return {"type": "unavailable", "message": "文件较大，请在 Finder 中查看。"}
        suffix = path.suffix.lower()
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
            return {"type": "image", "data": "data:" + mimetypes.guess_type(path)[0] + ";base64," + base64.b64encode(path.read_bytes()).decode()}
        if suffix in {".md", ".txt", ".json", ".csv"}:
            return {"type": "text", "text": path.read_text()[:100_000]}
        return {"type": "unavailable", "message": "此格式暂不支持内嵌预览，可以在 Finder 中查看。"}

    def open_thread(self, args):
        thread = self.thread(args["threadId"])
        open_url("codex://threads/" + thread["id"])
        return {"opened": True}

    def reveal(self, args):
        path = self.artifact_file(args)
        reveal(path)
        return {"opened": True}

    def dispatch(self, action, args):
        actions = {"overview": self.overview, "detail": self.detail, "addCategory": self.add_category,
                   "tagThread": self.tag_thread, "saveArtifact": self.save_artifact, "preview": self.preview,
                   "openThread": self.open_thread, "reveal": self.reveal}
        if action not in actions:
            raise ValueError("不支持的操作。")
        return actions[action](args)
