import json
from pathlib import Path
import sqlite3
import unittest
from src import event_tracker as e

def sample(filename):
    return json.loads((e.ROOT / "data" / "examples" / filename).read_text(encoding="utf-8-sig"))["材料"]

class ContractCases(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        e.initialize(self.db)
        self.initial=sample("D1-D5.json")
        self.extra=sample("D6-D8.json")
        e.ingest(self.db,self.initial+self.extra)
        self.items={r["编号"]:r for r in e.records(self.db,None)}

    def test_reprints_and_statement(self):
        for k in ("D2","D6"):
            self.assertEqual(self.items[k]["引述来源"],self.items["D1"]["来源"])
            self.assertEqual(self.items[k]["材料性质"],"转述")
        self.assertEqual([s["动作"] for s in self.items["D3"]["说法"]],["候选","尚未签约"])

    def test_project_and_amount(self):
        self.assertEqual(self.items["D4"]["项目"],"道路养护")
        self.assertEqual(self.items["D5"]["项目"],"照明改造")
        self.assertEqual(self.items["D4"]["金额"][0]["数值"],"800")
        self.assertEqual(self.items["D5"]["金额"][0]["数值"],"1200")
        for r in self.items.values():
            for c in r["说法"]:
                self.assertEqual(r["正文"][c["起点"]:c["终点"]],c["原句"])

    def test_as_of(self):
        ids=[r["编号"] for r in e.records(self.db,"2026-11-04 15:00")]
        self.assertNotIn("D5",ids)
        self.assertIn("D6",ids)
        self.assertIn("D5",[r["编号"] for r in e.records(self.db,"2026-11-05 18:00")])

    def test_unseen_and_denial(self):
        r=self.items["D7"]
        self.assertEqual((r["公司"],r["对手"],r["项目"]),("丙公司","港务集团","冷链仓储"))
        r=self.items["D8"]
        self.assertTrue(r["待复核"])
        self.assertNotIn("称已签约",[c["动作"] for c in r["说法"]])

    def test_retry_and_conflict(self):
        row=self.initial[0]
        counts,errors=e.ingest(self.db,[row, dict(row,编号="另一编号"),dict(row,正文="内容不同"),{},dict(row,编号="new",正文="其他材料。")])
        self.assertEqual(counts,{"新增":1,"重复":2,"失败":2})
        self.assertEqual(self.items["D1"]["正文"],self.db.execute("SELECT body FROM documents WHERE id='D1'").fetchone()[0])
        self.assertEqual(len(errors),2)

if __name__=="__main__":
    unittest.main()
