from hashlib import sha256
import json

from src.common.storage import link_document, stamp
from src.extract.contracts import extract
from src.extract.earnings import extract_earnings

REQUIRED = ("编号", "发布时间", "来源", "正文")

def ingest(db, rows, *, only=None):
    if not isinstance(rows, list):
        raise ValueError("需要材料数组，或含“材料”数组的对象")
    if only is not None and not 1 <= only <= len(rows):
        raise ValueError(f"重试序号 {only} 超出范围，批次共有 {len(rows)} 项")
    counts = dict.fromkeys(["新增","重复","失败"],0)
    errors = []
    selected = enumerate(rows, 1) if only is None else [(only, rows[only - 1])]
    for i, row in selected:
        try:
            if not isinstance(row, dict):
                raise ValueError("该项应为包含材料字段的对象")
            missing = [k for k in REQUIRED if not isinstance(row.get(k), str) or not row[k].strip()]
            if missing:
                raise ValueError("需要填写非空文本的字段为" + "、".join(missing))
            key,t,source,body = (row[k].strip() for k in REQUIRED)
            try:
                t = stamp(t)
            except ValueError:
                raise ValueError("披露时间无效，请填写有效的 YYYY-MM-DD HH:MM 日期时间") from None
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
                result = extract_earnings(source, body) or extract(source, body)
                db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?)",(key,t,source,body,fp,json.dumps(result,ensure_ascii=False)))
                link_document(db, key, result)
            counts["新增"]+=1
        except (ValueError, TypeError) as err:
            counts["失败"]+=1
            doc = row.get("编号") if isinstance(row, dict) else None
            label = f"（{doc.strip()}）" if isinstance(doc, str) and doc.strip() else ""
            errors.append(f"第{i}项{label}：{err}")
    return counts,errors
