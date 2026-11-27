"""从公开开发样例的副本，经 CLI、本机工作台和导出入口验证第四阶段。"""
from contextlib import closing, contextmanager
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from urllib.parse import urlencode
from urllib.request import ProxyHandler, build_opener

from eval.test_event_tracker import sample
from src.event_tracker import ROOT


@contextmanager
def workbench(db):
    server = subprocess.Popen(
        [sys.executable, "-m", "app.local", "--no-browser", "--db", str(db)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        env=dict(os.environ, PYTHONUTF8="1"), encoding="utf-8")
    try:
        url = re.search(r"http://127\.0\.0\.1:\d+", server.stdout.readline()).group()
        opener = build_opener(ProxyHandler({}))

        def read(path, form=None):
            data = urlencode(form).encode() if form is not None else None
            with opener.open(url + path, data=data, timeout=5) as response:
                return response.read().decode()
        yield read
    finally:
        server.terminate()
        server.wait(timeout=5)
        server.stdout.close()


class FourthStageAcceptance(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "trial.sqlite3"
        self.batch = Path(tmp.name) / "试用材料副本.json"
        self.rows = sample("F01-F03.json")

    def write_batch(self, rows):
        self.batch.write_text(json.dumps({"材料": rows}, ensure_ascii=False), encoding="utf-8")

    def attempt(self, expected_code, *args):
        result = subprocess.run(
            [sys.executable, "-m", "src.event_tracker", "--db", str(self.db), "import", str(self.batch), *args],
            cwd=ROOT, env=dict(os.environ, PYTHONUTF8="1"), capture_output=True, encoding="utf-8", timeout=10)
        self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        return result.stdout

    def test_bad_file_and_invalid_retry(self):
        self.batch.write_text('{"材料": [', encoding="utf-8")
        self.assertIn("第 1 行", self.attempt(1))
        self.write_batch(self.rows)
        self.assertIn("超出范围", self.attempt(1, "--only", "4"))
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM documents").fetchone()[0], 0)

    def test_partial_retry_review_export_and_restart(self):
        first, contract, earnings = self.rows
        self.write_batch([first, dict(contract, 正文=""), earnings])
        failure = self.attempt(1)
        self.assertIn("'新增': 2", failure)
        self.assertIn("第2项（F02）", failure)
        self.assertIn("正文", failure)
        self.write_batch(self.rows)
        retry = self.attempt(0, "--only", "2")
        self.assertIn("'新增': 1, '重复': 0", retry)
        query = "/brief?" + urlencode(dict(company="津桥公司", start=first["发布时间"], end="2099-01-01 00:00"))
        with workbench(self.db) as read:
            before = read(query)
            self.assertIn("金额待核", before)
            page = read("/")
            token = re.search(r'name="token" value="([^"]+)"', page)[1]
            self.assertIn("F02 · 待处理", page)
            self.assertIn(contract["正文"], page)
            saved = read("/amount-review", dict(token=token, document="F02", revision=0, reviewer="作者自测",
                                                reason="490万元为初稿，原句载明最终签约价为465万元", amount="465万元"))
            self.assertIn("F02 · 已复核", saved)
            exported = read(query + "&download=1")
            self.assertIn("490万元 → 465万元", exported)
            self.assertIn(contract["正文"], exported)
            self.assertNotIn("秋沅公司", exported)
        self.assertIn("'新增': 0, '重复': 3", self.attempt(0))
        with workbench(self.db) as read:
            self.assertIn("F02 · 已复核", read("/"))
            self.assertEqual(read(query + "&download=1"), exported)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM documents").fetchone()[0], 3)
            self.assertEqual(db.execute("SELECT count(*) FROM amount_reviews").fetchone()[0], 1)
