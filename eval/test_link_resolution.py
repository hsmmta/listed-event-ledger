import sqlite3
import unittest

from app.preview import report
from eval.test_event_tracker import sample
from src.common.storage import initialize, records
from src.ingest.materials import ingest


class LinkResolution(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        initialize(self.db)
        self.batch = sample("B01-B08.json")
        counts, errors = ingest(self.db, self.batch[::-1])
        self.assertEqual((counts["新增"], errors), (8, []))

    def read(self, until=None):
        return {row["编号"]: row for row in records(self.db, until)}

    def test_number_alias_and_review(self):
        rows = self.read()
        for doc in ["B02", "B06"]:
            self.assertEqual(rows[doc]["事项编号"], rows["B01"]["事项编号"])
        self.assertEqual(rows["B08"]["事项编号"], rows["B03"]["事项编号"])
        self.assertEqual(len({rows[k]["事项编号"] for k in ["B01", "B03", "B04"]}), 3)
        self.assertIsNone(rows["B05"]["事项编号"])
        self.assertEqual(rows["B05"]["候选合同编号"], ["HT-01", "HT-02"])
        self.assertEqual(rows["B07"]["候选合同编号"], [])
        refs = rows["B06"]["归并证据"]
        self.assertTrue({"B02", "B06"} <= {ref["材料"] for ref in refs})
        for row in rows.values():
            for ref in row["归并证据"]:
                body = rows[ref["材料"]]["正文"]
                self.assertEqual(body[ref["起点"]:ref["终点"]], ref["引句"])

    def test_later_alias_and_number_do_not_travel_back_in_time(self):
        early = dict(self.batch[5], 编号="E1", 发布时间="2026-11-09 09:00",
                     正文="澄浦公司与河口集团签订北港冷链中心项目合同。")
        ingest(self.db, [early])
        before = self.read("2026-11-15 08:59")
        after = self.read("2026-11-15 09:00")
        self.assertNotEqual(before["E1"]["事项编号"], before["B01"]["事项编号"])
        self.assertEqual(after["E1"]["事项编号"], after["B01"]["事项编号"])
        self.assertNotIn("B06", report(list(before.values()), "2026-11-15 08:59"))
        self.assertNotIn("HT-02", report(list(self.read("2026-11-11 23:59").values()), "2026-11-11 23:59"))

    def test_old_contract_reference_and_multiple_numbers_stay_pending(self):
        for i, field in enumerate(["原合同编号为HT-01", "合同编号为HT-01，合同编号为HT-02", "合同编号为HT-01/增补"]):
            row = dict(self.batch[0], 编号=f"X{i}", 正文="公司与河口集团签订北港仓储项目合同，" + field + "。")
            ingest(self.db, [row])
            self.assertIsNone(self.read()[row["编号"]]["事项编号"])

    def test_alias_without_contract_number(self):
        base = dict(self.batch[0], 来源="汀桥公司公告", 编号="Q1", 正文="公司与河口集团签订园区供水项目合同。")
        short = dict(base, 编号="Q2", 正文="公司与河口集团签订南线供水项目合同。“园区供水”简称“南线供水”。")
        ingest(self.db, [base, short])
        rows = self.read()
        self.assertEqual(rows["Q1"]["事项编号"], rows["Q2"]["事项编号"])

    def test_conflicting_short_name_and_other_counterparty(self):
        base = self.batch[0]
        short = "公司与河口集团签订北港短称项目合同。"
        for i, full in enumerate(["北港仓储", "北港冷库"]):
            row = dict(base, 编号=f"S{i}", 正文=short + f'“北港短称”为“{full}”的简称。')
            ingest(self.db, [row])
        separate = dict(base, 编号="T1", 正文=base["正文"].replace("河口集团", "林海集团"))
        ingest(self.db, [separate])
        rows = self.read()
        self.assertNotEqual(rows["T1"]["事项编号"], rows["B01"]["事项编号"])
        self.assertIsNone(rows["S0"]["事项编号"])
        self.assertEqual(rows["S0"]["候选合同编号"], ["HT-01", "HT-02"])
        self.assertIn("北港冷库", " ".join(rows["S0"]["待复核"]))
