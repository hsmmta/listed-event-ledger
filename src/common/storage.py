from datetime import datetime
import json


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
    if db.execute("PRAGMA user_version").fetchone()[0] == 0:
        with db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("PRAGMA user_version").fetchone()[0] == 0:
                old_rows = db.execute(
                    "SELECT id, result FROM documents LEFT JOIN document_matters ON document_id=id "
                    "WHERE document_id IS NULL ORDER BY published, id")
                for document_id, result in old_rows.fetchall():
                    link_document(db, document_id, json.loads(result))
                db.execute("PRAGMA user_version = 1")


def records(db, until):
    query = """
        SELECT id, published, source, body, result, matter_id
        FROM documents LEFT JOIN document_matters ON documents.id = document_matters.document_id
        WHERE published <= ? ORDER BY published, id
    """
    return [{"编号": k, "发布时间": t, "来源": s, "正文": b, **json.loads(result),
             "事项编号": f"HT-{matter_id:04d}" if matter_id is not None else None}
            for k, t, s, b, result, matter_id in db.execute(query, (until or "9999",))]
