from contextlib import closing
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import unittest

from app.preview import report
from eval.score_links import compare
from eval.test_event_tracker import sample
from src.common.storage import initialize, records
from src.ingest.materials import ingest


class ContractAcceptance(unittest.TestCase):
    def setUp(self):
        self.materials = sample("C01-C07.json")
        path = Path(__file__).parent / "expected" / "二阶段验收.json"
        self.expected = json.loads(path.read_text(encoding="utf-8"))
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        initialize(self.db)
        counts, errors = ingest(self.db, self.materials)
        self.assertEqual((counts, errors), ({"新增": 7, "重复": 0, "失败": 0}, []))

    def test_contracts_status_amounts_and_sources(self):
        rows = records(self.db, None)
        actual = {r["编号"]: r["事项编号"] for r in rows}
        pairs = compare({doc: e["归属"] for doc, e in self.expected.items()}, actual)
        self.assertEqual([len(pairs[k]) for k in ("正确同组", "正确分开", "错并", "漏并", "未决")],
                         [6, 9, 0, 0, 0])
        self.assertEqual([doc for doc, group in actual.items() if group is None], ["C06"])
        for r in rows:
            with self.subTest(doc=r["编号"]):
                e = self.expected[r["编号"]]
                self.assertEqual([c["动作"] for c in r["说法"]], e["动作"])
                self.assertEqual([[v["原文角色"], v["数值"], v["单位"]] for v in r["金额"]], e["金额"])
                for c in r["说法"]:
                    self.assertEqual(r["正文"][c["起点"]:c["终点"]], c["原句"])
                if r["编号"] == "C06":
                    self.assertEqual(r["候选合同编号"], ["JC-718", "JC-903"])

    def test_each_disclosure_against_incremental_import(self):
        with closing(sqlite3.connect(":memory:")) as prefix:
            initialize(prefix)
            for item in self.materials:
                t = item["发布时间"]
                before = (datetime.fromisoformat(t) - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
                with self.subTest(cutoff=t):
                    self.assertEqual(records(self.db, before), records(prefix, None))
                    ingest(prefix, [item])
                    rows = records(self.db, t)
                    self.assertEqual(rows, records(prefix, None))
                    visible = {r["编号"]: r["正文"] for r in rows}
                    for row in rows:
                        for ref in row["归并证据"]:
                            self.assertEqual(visible[ref["材料"]][ref["起点"]:ref["终点"]], ref["引句"])
        past = report(records(self.db, "2026-11-19 15:59"), "2026-11-19 15:59")
        self.assertIn("尚未签约", past)
        for future in ("435万元", "JC-718", "C03"):
            self.assertNotIn(future, past)
