"""导入材料并导出抽取结果。请从项目根目录运行 python -m src.event_tracker。"""
import argparse
import json
from pathlib import Path
import sqlite3
from app.preview import report
from src.ingest.materials import ingest
from src.common.storage import DDL, records, stamp

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",type=Path,default=ROOT/"data"/"interim"/"事件资料.sqlite3")
    cmd=parser.add_subparsers(dest="action",required=True)
    cmd.add_parser("import").add_argument("file",type=Path)
    show=cmd.add_parser("show")
    show.add_argument("--until",type=stamp)
    show.add_argument("--html",type=Path)
    show.add_argument("--json", type=Path, help="保存结构化结果")
    args=parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as db:
        db.executescript(DDL)
        if args.action=="import":
            payload=json.loads(args.file.read_text(encoding="utf-8-sig"))
            counts,errors=ingest(db,payload.get("材料") if isinstance(payload,dict) else payload)
            print(counts,*errors,sep="\n")
            return int(bool(errors))
        rows=records(db,args.until)
        if args.json:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
        if args.html:
            args.html.parent.mkdir(parents=True, exist_ok=True)
            args.html.write_text(report(rows,args.until),encoding="utf-8")
            print(args.html)
        elif not args.json:
            print(json.dumps(rows,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
