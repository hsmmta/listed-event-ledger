from hashlib import sha256
import json

from src.common.storage import link_document, stamp
from src.extract.contracts import extract

REQUIRED = ("编号", "发布时间", "来源", "正文")

def ingest(db, rows):
    if not isinstance(rows, list):
        raise ValueError("需要材料数组，或含“材料”数组的对象")
    counts = dict.fromkeys(["新增","重复","失败"],0)
    errors = []
    for i,row in enumerate(rows,1):
        try:
            if not isinstance(row,dict) or any(not isinstance(row.get(k),str) or not row[k].strip() for k in REQUIRED):
                raise ValueError("编号、发布时间、来源、正文均须为非空文本")
            key,t,source,body = (row[k].strip() for k in REQUIRED)
            t = stamp(t)
            fp = sha256(json.dumps([t,source,body],ensure_ascii=False).encode()).hexdigest()
            with db:
                if not db.in_transaction:
                    db.execute("BEGIN IMMEDIATE")
                prior = db.execute("SELECT fingerprint FROM documents WHERE id=?", (key,)).fetchone()
                if prior and prior[0]!=fp:
                    raise ValueError("编号已有不同内容，请核查版本")
                if prior or db.execute("SELECT 1 FROM documents WHERE fingerprint=?",(fp,)).fetchone():
                    counts["重复"]+=1
                    continue
                result=extract(source,body)
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?)",(key,t,source,body,fp,json.dumps(result,ensure_ascii=False)))
                link_document(db, key, result)
            counts["新增"]+=1
        except (ValueError, TypeError) as err:
            counts["失败"]+=1
            errors.append(f"第{i}项：{err}")
    return counts,errors
