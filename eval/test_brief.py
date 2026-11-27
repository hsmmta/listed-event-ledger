import re
import sqlite3
import unittest

from app.brief import brief
from eval.test_event_tracker import sample
from src.common.storage import initialize
from src.ingest.materials import ingest
from src.verify.amount_review import correct_amount


class BriefTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        initialize(self.db)
        for path in ("来源与业绩.json", "E01-E05.json", "R01-金额复核.json"):
            ingest(self.db, sample(path))

    def test_company_correction_and_early_cutoff(self):
        start = "2026-11-18 16:00"
        early = brief(self.db, "渚江公司", start, "2026-11-20 15:59")
        late = brief(self.db, "渚江公司", start, "2026-11-21 16:00")
        self.assertNotIn("608万元", early)
        self.assertIn("680万元", early)
        self.assertIn("公司更正披露", late)
        self.assertIn("原披露 680万元，本次更正为 608万元", late)
        self.assertIn("作用范围待核", late)
        self.assertNotIn("望汀", late)
        for anchor in re.findall(r'href="#([^"]+)"', late):
            self.assertEqual(late.count(f'id="{anchor}"'), 1)

    def test_earnings_and_manual_review(self):
        early = brief(self.db, "望汀公司", "2026-01-01 00:00", "2026-03-18 17:59")
        self.assertNotIn("658万元", early)
        late = brief(self.db, "望汀公司", "2026-03-18 17:59", "2026-03-18 18:00")
        self.assertIn("实际 658万元", late)
        correct_amount(self.db, "R01", 0, "608万元", "试用员", "草案金额误抽")
        self.db.execute("UPDATE amount_reviews SET reviewed='2026-11-23 10:00:00+08:00'")
        early = brief(self.db, "清浦公司", "2026-11-22 15:59", "2026-11-23 09:59")
        self.assertNotIn("试用员", early)
        self.assertIn("金额待核", early)
        late = brief(self.db, "清浦公司", "2026-11-23 09:59", "2026-11-23 10:00")
        self.assertIn("研究者修正抽取", late)
        self.assertIn("680万元 → 608万元", late)
        self.assertIn("试用员", late)
        self.assertNotIn("公司更正披露", late)
