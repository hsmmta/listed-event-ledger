from datetime import datetime
import json

DDL = """
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY, published TEXT NOT NULL, source TEXT NOT NULL,
 body TEXT NOT NULL, fingerprint TEXT UNIQUE NOT NULL, result TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS published_idx ON documents(published);
"""

def stamp(value):
    return datetime.strptime(value, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %H:%M")

def records(db, until):
    return [{"编号":k,"发布时间":t,"来源":s,"正文":b,**json.loads(result)}
            for k,t,s,b,result in db.execute("SELECT id,published,source,body,result FROM documents WHERE published<=? ORDER BY published,id",(until or "9999",))]
