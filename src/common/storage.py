from datetime import datetime
import json

from src.extract.earnings import extract_earnings
from src.link.resolve import resolve, stable_id
from src.verify.sources import trace
from src.verify.contracts import verify
from src.extract.contracts import SIGNING_TOPIC, extract


DDL = """
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY, published TEXT NOT NULL, source TEXT NOT NULL,
 body TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL, result TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS published_idx ON documents(published);
CREATE TABLE IF NOT EXISTS matters(
 id INTEGER PRIMARY KEY, company TEXT NOT NULL, party TEXT NOT NULL, project TEXT NOT NULL,
 UNIQUE(company, party, project));
CREATE TABLE IF NOT EXISTS document_matters(
 document_id TEXT PRIMARY KEY REFERENCES documents(id), matter_id INTEGER NOT NULL REFERENCES matters(id));
"""


def stamp(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")


def link_document(db, document_id, result):
    fields = tuple(result[k] for k in ("公司", "对手", "项目"))
    if result["待复核"] or not all(fields):
        return
    db.execute("INSERT INTO matters(company, party, project) VALUES(?, ?, ?) "
               "ON CONFLICT(company, party, project) DO NOTHING", fields)
    db.execute("INSERT INTO document_matters(document_id, matter_id) "
               "SELECT ?, id FROM matters WHERE company=? AND party=? AND project=?",
               (document_id, *fields))


def initialize(db):
    db.executescript(DDL)
    if db.execute("PRAGMA user_version").fetchone()[0] >= 3:
        return
    with db:
        db.execute("BEGIN IMMEDIATE")
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version >= 3:
            return
        rows = db.execute("SELECT id, source, body, result FROM documents ORDER BY published, id")
        for document_id, source, body, stored in rows:
            earnings = extract_earnings(source, body)
            if earnings or (version < 2 and SIGNING_TOPIC.search(body)):
                result = earnings or extract(source, body)
                db.execute("UPDATE documents SET result=? WHERE id=?",
                           (json.dumps(result, ensure_ascii=False), document_id))
                db.execute("DELETE FROM document_matters WHERE document_id=?", (document_id,))
            elif version == 0:
                result = json.loads(stored)
            else:
                continue
            link_document(db, document_id, result)
        db.execute("PRAGMA user_version = 3")


def records(db, until):
    query = """
        SELECT id, published, source, body, result, matter_id
        FROM documents LEFT JOIN document_matters ON documents.id = document_matters.document_id
        WHERE published <= ? ORDER BY published, id
    """
    rows = [{"编号": k, "发布时间": t, "来源": s, "正文": b, **json.loads(result),
             "事项编号": f"HT-{matter_id:04d}" if matter_id is not None else None}
            for k, t, s, b, result, matter_id in db.execute(query, (until or "9999",))]
    resolve(rows)
    for row in rows:
        if row.get("事件类型") == "业绩" and not row["待复核"]:
            row["事项编号"] = stable_id((row["公司"], row["报告期"]), "业绩", row["指标"])
            row["归并依据"] = "按公告公司、报告期和指标归属"
    return verify(trace(rows))
