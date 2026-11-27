"""导入材料并导出抽取结果。请从项目根目录运行 python -m src.event_tracker。"""
import argparse
import json
from pathlib import Path
import sqlite3
from app.preview import report
from src.ingest.materials import ingest
from src.common.storage import initialize, records, stamp

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",type=Path,default=ROOT/"data"/"interim"/"事件资料.sqlite3")
    cmd=parser.add_subparsers(dest="action",required=True)
    importer = cmd.add_parser("import")
    importer.add_argument("file", type=Path)
    importer.add_argument("--only", type=int, metavar="序号", help="只导入原批次指定的一项，从 1 起算")
    show=cmd.add_parser("show")
    show.add_argument("--until",type=stamp)
    show.add_argument("--html",type=Path)
    show.add_argument("--json", type=Path, help="保存结构化结果")
    args=parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(args.db) as db:
        initialize(db)
        if args.action=="import":
            try:
                payload = json.loads(args.file.read_text(encoding="utf-8-sig"))
                rows = payload.get("材料") if isinstance(payload, dict) else payload
                counts, errors = ingest(db, rows, only=args.only)
            except json.JSONDecodeError as err:
                print(f"{args.file} 的 JSON 无法解析，请核对第 {err.lineno} 行、第 {err.colno} 列")
                return 1
            except (OSError, ValueError) as err:
                print(f"无法导入 {args.file}：{err}")
                return 1
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
