"""对合同原句中的多个金额进行人工复核。记录绑定材料指纹，原始抽取始终保留。"""
from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re

from src.extract.contracts import AMOUNT_FIELD
from src.link.resolve import SENTENCE


DATA = Path(__file__).resolve().parents[2] / "data"
DEFAULT_DB = DATA / "interim" / "事件资料.sqlite3"
MONEY = re.compile(r"(?<![\d.,])([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(亿元|万元|元)")
COLUMNS = """(
 id INTEGER PRIMARY KEY, document_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 reviewed TEXT NOT NULL, old TEXT NOT NULL, new TEXT NOT NULL, reviewer TEXT NOT NULL,
 reason TEXT NOT NULL, start INTEGER NOT NULL, end INTEGER NOT NULL)"""


def ledger(db):
    databases = {name: path for _, name, path in db.execute("PRAGMA database_list")}
    if databases["main"] and Path(databases["main"]).resolve() == DEFAULT_DB.resolve():
        if "audit" not in databases:
            path = DATA / "reviews" / "人工纠错.sqlite3"
            path.parent.mkdir(parents=True, exist_ok=True)
            db.execute("ATTACH DATABASE ? AS audit", (str(path),))
        return "audit.amount_reviews"
    return "main.amount_reviews"


def initialize_reviews(db):
    table = ledger(db)
    db.execute(f"CREATE TABLE IF NOT EXISTS {table}{COLUMNS}")


def review_field(body, result):
    amounts = result["金额"]
    if len(amounts) != 1 or amounts[0]["原文角色"] != "合同金额":
        return None
    original = amounts[0]["数值"] + amounts[0]["单位"]
    field = AMOUNT_FIELD.search(body)
    if not field or field[1] != "合同金额":
        return None
    for sentence in SENTENCE.finditer(body):
        quote = sentence.group()
        if not sentence.start() <= field.start() < sentence.end():
            continue
        options = list(dict.fromkeys(n + u for n, u in MONEY.findall(quote)))
        if len(options) > 1 and original in options:
            return {"机器原值": original, "可选金额": options, "原句": quote,
                    "起点": sentence.start(), "终点": sentence.end(), "记录": []}
    return None


def apply_reviews(db, rows, until):
    table = ledger(db)
    history = defaultdict(list)
    query = f"""SELECT a.document_id, a.id, a.reviewed, a.old, a.new, a.reviewer, a.reason, a.start, a.end
                FROM {table} a JOIN documents d ON (a.document_id=d.id AND a.fingerprint=d.fingerprint)
                WHERE d.published <= ? AND substr(a.reviewed,1,16) <= ? ORDER BY a.id"""
    for doc, *values in db.execute(query, (until or "9999", until or "9999")):
        history[doc].append(dict(zip(("序号", "处理时间", "原值", "新值", "处理人", "理由", "起点", "终点"), values)))
    for row in rows:
        task = review_field(row["正文"], row)
        if task:
            row["金额复核"] = task
            task["记录"] = edits = history[row["编号"]]
            if edits:
                amount = MONEY.fullmatch(edits[-1]["新值"])
                row["金额"][0].update(数值=amount[1], 单位=amount[2])


def correct_amount(db, document_id, revision, value, reviewer, reason):
    reviewer, reason = reviewer.strip(), reason.strip()
    if not reviewer or not reason or len(reviewer) > 80 or len(reason) > 1000:
        raise ValueError("请填写处理人（最多 80 字）和理由（最多 1000 字）")
    table = ledger(db)
    with db:
        db.execute("BEGIN IMMEDIATE")
        doc = db.execute("SELECT body, result, fingerprint FROM documents WHERE id=?", (document_id,)).fetchone()
        task = review_field(doc[0], json.loads(doc[1])) if doc else None
        if not task or value not in task["可选金额"]:
            raise ValueError("请从这条材料的原句中选择合同金额")
        last = db.execute(f"SELECT id, new FROM {table} WHERE document_id=? AND fingerprint=? "
                          "ORDER BY id DESC LIMIT 1", (document_id, doc[2])).fetchone()
        expected, old = last or (0, task["机器原值"])
        if revision != expected:
            raise ValueError("记录已更新，请刷新页面后重新核对")
        if last and old == value:
            raise ValueError("该金额已复核，请选择需要修正的金额")
        reviewed = datetime.now().astimezone().isoformat(sep=" ", timespec="seconds")
        db.execute(f"INSERT INTO {table}(document_id,fingerprint,reviewed,old,new,reviewer,reason,start,end) "
                   "VALUES(?,?,?,?,?,?,?,?,?)",
                   (document_id, doc[2], reviewed, old, value, reviewer, reason, task["起点"], task["终点"]))
