from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json
import sqlite3
import unittest

from app.preview import report
from src.common import storage
from src.verify.amount_review import correct_amount
from src.ingest.materials import ingest


class AmountReviewTest(unittest.TestCase):
    def test_review_uses_source_and_preserves_extraction_and_history(self):
        body = "公司与东潮集团签订滨海项目合同，合同金额为680万元系草案数据，本次签约金额以608万元为准。"
        with closing(sqlite3.connect(":memory:")) as db:
            storage.initialize(db)
            ingest(db, [{"编号": "T", "发布时间": "2025-01-01 08:00", "来源": "甲公司公告", "正文": body}])
            row = storage.records(db, None)[0]
            self.assertIn("金额复核", row)
            self.assertIn("1 条金额待处理", report([row], ""))
            self.assertEqual(row["金额复核"]["可选金额"], ["680万元", "608万元"])
            for value, person, why in [("999万元", "甲", "原文"), ("608万元", "", "原文"), ("608万元", "甲", " ")]:
                with self.assertRaises(ValueError):
                    correct_amount(db, "T", 0, value, person, why)
            correct_amount(db, "T", 0, "608万元", "甲", "草案数被误抽")
            row = storage.records(db, None)[0]
            self.assertEqual(row["金额"][0]["数值"], "608")
            edit = row["金额复核"]["记录"][0]
            self.assertEqual((edit["原值"], edit["新值"], edit["处理人"], edit["理由"]),
                             ("680万元", "608万元", "甲", "草案数被误抽"))
            self.assertEqual(body[edit["起点"]:edit["终点"]], body)
            self.assertTrue(edit["处理时间"])
            original = json.loads(db.execute("SELECT result FROM documents").fetchone()[0])
            self.assertEqual(original["金额"][0]["数值"], "680")
            past = storage.records(db, "2025-01-01 08:00")[0]
            self.assertEqual((past["金额"][0]["数值"], past["金额复核"]["记录"]), ("680", []))
            with self.assertRaises(ValueError):
                correct_amount(db, "T", 0, "680万元", "乙", "旧页面")
            correct_amount(db, "T", edit["序号"], "680万元", "乙", "复查")
            self.assertEqual(len(storage.records(db, None)[0]["金额复核"]["记录"]), 2)

    def test_rebuilt_default_db_restores_only_matching_materials(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            working = root / "materials.sqlite3"
            item = {"编号": "T", "来源": "甲公司公告", "发布时间": "2025-01-01 08:00",
                    "正文": "公司与山海集团签署水厂项目合同，合同金额为18万元系预算，签约价为21万元。"}
            with patch("src.verify.amount_review.DEFAULT_DB", working), patch("src.verify.amount_review.DATA", root):
                with closing(sqlite3.connect(working)) as db:
                    storage.initialize(db)
                    ingest(db, [item])
                    correct_amount(db, "T", 0, "21万元", "甲", "核查签约价")
                working.rename(root / "previous.sqlite3")
                with closing(sqlite3.connect(working)) as db:
                    storage.initialize(db)
                    ingest(db, [dict(item, 正文=item["正文"].replace("18万元", "28万元"))])
                    self.assertEqual(storage.records(db, None)[0]["金额复核"]["记录"], [])
                working.rename(root / "different.sqlite3")
                with closing(sqlite3.connect(working)) as db:
                    storage.initialize(db)
                    ingest(db, [item])
                    restored = storage.records(db, None)[0]
                    self.assertEqual(restored["金额复核"]["记录"][0]["新值"], "21万元")
                    self.assertEqual(restored["金额"][0]["数值"], "21")
