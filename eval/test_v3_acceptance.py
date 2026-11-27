from datetime import datetime, timedelta
import json
import re
import sqlite3
import unittest

from app.preview import report
from eval.test_event_tracker import sample
from src.common.storage import initialize, records
from src.ingest.materials import ingest


class DualTypeAcceptance(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        initialize(self.db)
        self.batch = sample("来源与业绩.json") + sample("E01-E05.json")
        self.assertEqual(ingest(self.db, self.batch[::-1])[0]["新增"], len(self.batch))
        self.rows = {r["编号"]: r for r in records(self.db, None)}

    def test_reprint_roots_and_missing_original(self):
        for doc, chain in (("S01", ["S01"]), ("S02", ["S01","S02"]), ("S03", ["S01","S02","S03"])):
            refs = self.rows[doc]["出处判断"][0]["报道链"]
            self.assertEqual([r["材料"] for r in refs], chain)
            self.assertEqual(refs[0]["发布时间"], "2026-11-01 09:00")
            for ref in refs:
                self.assertEqual(self.rows[ref["材料"]]["正文"][ref["起点"]:ref["终点"]], ref["引句"])
        for doc in ("S04", "S05"):
            self.assertFalse(self.rows[doc]["出处判断"][0]["报道链"])
        page = report(records(self.db, "2026-11-02 08:00"), "")
        self.assertIn("3 份材料，1 条可追溯报道链", page)

    def test_earnings_values_and_scope(self):
        main = self.rows["P01"]["事项编号"]
        self.assertTrue(main)
        values = [("预告", "800", "1000"), ("修正", "620", "700"), ("实际", "658", "658"),
                  ("预告", "90", "110"), ("实际", "318", "318")]
        for i, (stage, low, high) in enumerate(values, 1):
            row = self.rows[f"P0{i}"]
            fact = row["业绩值"]
            self.assertEqual((fact["阶段"], fact["下限"], fact["上限"], fact["单位"]), (stage, low, high, "万元"))
            self.assertEqual(row["事项编号"] == main, i <= 3)
            claim = row["说法"][0]
            self.assertEqual(claim["原句"], row["正文"][claim["起点"]:claim["终点"]])
        self.assertIsNone(self.rows["P06"]["事项编号"])
        early = report(records(self.db, "2026-03-18 17:59"), "")
        self.assertNotIn("658万元", early)
        self.assertIn("620万元", early)

    def test_all_boundaries_and_click_targets(self):
        prefix = sqlite3.connect(":memory:")
        self.addCleanup(prefix.close)
        initialize(prefix)
        for item in sorted(self.batch, key=lambda r: r["发布时间"]):
            t = datetime.fromisoformat(item["发布时间"])
            before = (t - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
            # Compare material membership and evidence, since local basic IDs depend on insertion order.
            for cutoff, add in [(before, False), (item["发布时间"], True)]:
                if add:
                    ingest(prefix, [item])
                def snapshot(rows):
                    return [{k: v for k,v in r.items() if k != "事项编号"} for r in rows]
                self.assertEqual(snapshot(records(self.db, cutoff)), snapshot(records(prefix, None)))
        page = report(list(self.rows.values()), "")
        for anchor in re.findall(r'href="#([^"]+)"', page):
            self.assertEqual(page.count(f'id="{anchor}"'), 1)

    def test_mixed_story_source_and_changed_quote(self):
        source = self.batch[1]
        report_text = dict(source, 编号="S-mixed", 正文=source["正文"] + "本报记者现场获悉，望汀公司尚未签约。")
        changed = dict(source, 编号="S-changed", 正文=source["正文"].replace("项目合同。", "项目合同，合同金额为350万元。"))
        ingest(self.db, [report_text, changed])
        rows = {r["编号"]: r for r in records(self.db, None)}
        chains = [[v["材料"] for v in f["报道链"]] for f in rows["S-mixed"]["出处判断"]]
        self.assertEqual(chains, [["S01", "S-mixed"], ["S-mixed"]])
        self.assertEqual(rows["S-changed"]["出处判断"][0]["报道链"], [])

    def test_upgrade_old_earnings_and_ambiguous_values(self):
        old = self.rows["P03"]
        with self.db:
            self.db.execute("UPDATE documents SET result=? WHERE id='P03'",
                            (json.dumps({"公司": old["公司"], "项目": "", "对手": "", "待复核": ["缺少合同动作"]}),))
            self.db.execute("PRAGMA user_version=2")
        initialize(self.db)
        rows = {r["编号"]: r for r in records(self.db, None)}
        self.assertEqual(rows["P03"], old)
        for i, figure in enumerate(["10亿元至20万元", "10%至20%", "20万元至10万元"]):
            row = dict(self.batch[5], 编号=f"U{i}", 正文="2025年度业绩预告：预计归母净利润为" + figure + "。")
            ingest(self.db, [row])
            value = next(r for r in records(self.db, None) if r["编号"] == row["编号"])
            self.assertIsNone(value["事项编号"])
            self.assertIsNone(value["业绩值"])
