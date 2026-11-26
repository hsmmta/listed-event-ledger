import json
import sqlite3
import unittest
from contextlib import closing

from app.preview import report
from eval.test_event_tracker import sample
from src.common.storage import initialize, records
from src.ingest.materials import ingest


class FirstVersionAcceptance(unittest.TestCase):
    def test_signature_update_at_disclosure_minute(self):
        materials = sample("A1-A3.json")
        with closing(sqlite3.connect(":memory:")) as db:
            initialize(db)
            counts, errors = ingest(db, [*materials, materials[-1]])
            self.assertEqual((counts, errors), ({"新增": 3, "重复": 1, "失败": 0}, []))
            past = records(db, "2026-11-12 15:59")
            latest = records(db, "2026-11-12 16:00")
        self.assertEqual([r["编号"] for r in past], ["A1", "A2"])
        self.assertNotIn("260万元", report(past, "2026-11-12 15:59"))
        self.assertEqual([r["编号"] for r in latest], ["A1", "A2", "A3"])
        first, other, signed = latest
        self.assertTrue(first["事项编号"])
        self.assertEqual(first["事项编号"], signed["事项编号"])
        self.assertNotEqual(first["事项编号"], other["事项编号"])
        self.assertEqual([c["动作"] for c in first["说法"]], ["候选", "尚未签约"])
        self.assertEqual(signed["说法"], [{"动作": "称已签约", "原句": materials[-1]["正文"][10:],
                                      "起点": 10, "终点": 45}])
        page = report(latest, "2026-11-12 16:00")
        self.assertIn('href="#quote-4133-10-45"', page)
        self.assertIn("披露时间线", page)

    def test_stored_old_claim_is_repaired_once(self):
        signed = sample("A1-A3.json")[-1]
        with closing(sqlite3.connect(":memory:")) as db:
            initialize(db)
            ingest(db, [signed])
            matter = records(db, None)[0]["事项编号"]
            result = json.loads(db.execute("SELECT result FROM documents").fetchone()[0])
            wrong = {"动作": "称已签约", "原句": signed["正文"][:10], "起点": 0, "终点": 10}
            result["说法"] = [wrong, result["说法"][-1]]
            with db:
                db.execute("UPDATE documents SET result=?", (json.dumps(result, ensure_ascii=False),))
                db.execute("PRAGMA user_version=1")
            initialize(db)
            initialize(db)
            row = records(db, None)[0]
            self.assertEqual(row["事项编号"], matter)
            self.assertEqual(row["正文"], signed["正文"])
            self.assertEqual([c["原句"] for c in row["说法"]], [signed["正文"][10:]])
