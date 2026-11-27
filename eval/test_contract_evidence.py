from datetime import datetime, timedelta
import sqlite3
import unittest

from app.preview import report
from eval.test_event_tracker import sample
from src.common.storage import initialize, records
from src.ingest.materials import ingest


class ContractEvidence(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        initialize(self.db)
        self.batch = sample("E01-E05.json")
        self.assertEqual(ingest(self.db, self.batch[::-1])[1], [])

    def test_relations_and_all_disclosure_boundaries(self):
        kinds = [[], ["反证"], ["后续签署"], ["金额更正"], []]
        for i, item in enumerate(self.batch):
            cutoff = datetime.fromisoformat(item["发布时间"])
            before = records(self.db, (cutoff - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M"))
            after = records(self.db, item["发布时间"])
            self.assertNotIn(item["编号"], [r["编号"] for r in before])
            self.assertEqual([f["关系"] for f in after[-1]["核验"]], kinds[i])
            visible = {r["编号"]: r for r in after}
            for row in after:
                for link in row["核验"]:
                    for ref in link["依据"]:
                        self.assertEqual(visible[ref["材料"]]["正文"][ref["起点"]:ref["终点"]], ref["引句"])
            if i == 3:
                self.assertNotIn("608万元", report(before, "2026-11-20 15:59"))
                self.assertEqual(after[-1]["事项编号"], after[-2]["事项编号"])
                self.assertEqual([x["材料"] for x in after[-1]["核验"][0]["依据"]], ["E03", "E04"])
        self.assertIsNone(after[-1]["事项编号"])

    def test_unmatched_old_value_or_issuer(self):
        for i, changes in enumerate(({"来源":"岭原公司公告"}, {"正文":self.batch[3]["正文"].replace("680万元","681万元")})):
            row = dict(self.batch[3], 编号=f"X{i}", **changes)
            ingest(self.db, [row])
            result = next(r for r in records(self.db, None) if r["编号"] == row["编号"])
            self.assertTrue(result["待复核"])
            self.assertIsNone(result["事项编号"])
            self.assertFalse(result["核验"])

    def test_no_later_signing_inference_from_publication_date_alone(self):
        for value in ("2026年11月17日", "2026年11月18日", "近日"):
            row = dict(self.batch[2], 编号="签约" + value,
                       正文=self.batch[2]["正文"].replace("2026年11月19日", value))
            ingest(self.db, [row])
            signed = next(r for r in records(self.db, None) if r["编号"] == row["编号"])
            self.assertFalse(signed["核验"])

    def test_entire_snapshot_equal_to_only_visible_inputs(self):
        prefix = sqlite3.connect(":memory:")
        self.addCleanup(prefix.close)
        initialize(prefix)
        for item in self.batch:
            t = datetime.fromisoformat(item["发布时间"])
            before = (t - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
            self.assertEqual(records(self.db, before), records(prefix, None))
            ingest(prefix, [item])
            self.assertEqual(records(self.db, item["发布时间"]), records(prefix, None))
