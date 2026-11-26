import json
from contextlib import closing
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from app.local import make_server
from app.preview import report
from eval.test_event_tracker import sample
from src.common.storage import records
from src.extract.contracts import extract
from src.ingest.materials import ingest


class EvidenceCases(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "store.sqlite3"

    def start_application(self):
        with make_server(self.path):
            pass

    def test_import_repeat_restart_and_disclosure_time(self):
        self.start_application()
        earlier = dict(编号="新材料甲", 发布时间="2026-11-07 10:00", 来源="晴川公司公告",
                       正文="会议结束。公司与林海集团签订节水改造项目合同。")
        later = dict(earlier, 编号="新材料乙", 发布时间="2026-11-08 12:00",
                     正文="进展如下。公司与林海集团签订节水改造项目合同，合同金额为80万元。")
        with closing(sqlite3.connect(self.path)) as db:
            counts, errors = ingest(db, [earlier, later, later])
            self.assertEqual((counts, errors), ({"新增": 2, "重复": 1, "失败": 0}, []))
            original = records(db, None)
            self.assertTrue(original[0].get("事项编号"))
            self.assertEqual(original[0]["事项编号"], original[1]["事项编号"])
        self.start_application()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(records(db, None), original)
            past = records(db, "2026-11-08 11:59")
            self.assertEqual(past, original[:1])
            self.assertNotIn("80万元", report(past, "2026-11-08 11:59"))
            claim = original[1]["说法"][0]
            self.assertEqual(later["正文"][claim["起点"]:claim["终点"]], claim["原句"])

    def test_upgrade_existing_materials_without_reextracting(self):
        inputs = sample("D1-D5.json") + sample("D6-D8.json")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE documents(id TEXT PRIMARY KEY, published TEXT, source TEXT, "
                       "body TEXT, fingerprint TEXT UNIQUE, result TEXT)")
            for r in inputs:
                result = json.dumps(extract(r["来源"], r["正文"]), ensure_ascii=False)
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?)",
                           (r["编号"], r["发布时间"], r["来源"], r["正文"], r["编号"], result))
            before = db.execute("SELECT * FROM documents ORDER BY id").fetchall()
        self.start_application()
        self.start_application()
        with closing(sqlite3.connect(self.path)) as db:
            rows = {r["编号"]: r for r in records(db, None)}
            self.assertTrue(rows["D3"].get("事项编号"))
            self.assertEqual(rows["D3"]["事项编号"], rows["D5"]["事项编号"])
            self.assertNotEqual(rows["D4"]["事项编号"], rows["D5"]["事项编号"])
            self.assertIsNone(rows["D8"]["事项编号"])
            self.assertEqual(db.execute("SELECT * FROM documents ORDER BY id").fetchall(), before)

    def test_two_claims_link_to_one_escaped_source_span(self):
        self.start_application()
        row = dict(编号="记录<一>", 发布时间="2026-11-07 09:00", 来源="晴川公司公告",
                   正文="说明<&>。公司为园区乙节水改造项目第一候选人，双方尚未签订正式合同。后续见公告。")
        with closing(sqlite3.connect(self.path)) as db:
            ingest(db, [row])
            page = report(records(db, None), "")
        targets = re.findall(r'href="#(quote-[^"]+)"', page)
        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0], targets[1])
        self.assertEqual(page.count(f'id="{targets[0]}"'), 1)
        self.assertIn('>公司为园区乙节水改造项目第一候选人，双方尚未签订正式合同。</mark>后续见公告。', page)
        self.assertIn("说明&lt;&amp;&gt;。", page)
