"""本机材料录入与历史查询页面。"""
import argparse
import json
import secrets
import sqlite3
import webbrowser
from contextlib import closing
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from app.preview import report
from src.common.storage import initialize, records, stamp
from src.ingest.materials import ingest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "interim" / "事件资料.sqlite3"

EXAMPLES = {
    "/examples": ("D1-D5.json", "D6-D8.json"),
    "/stage-three": ("来源与业绩.json", "E01-E05.json"),
    "/evidence-examples": ("E01-E05.json",),
    "/link-examples": ("B01-B08.json",),
}


def controls(token, cutoff, notice):
    secret = f'<input type="hidden" name="token" value="{token}">'
    return f"""
<p role="status">{escape(notice)}</p>
<form method="get"><label>按披露时间回看（本地时间）
<input type="datetime-local" name="until" value="{escape(cutoff.replace(" ","T"))}"></label>
<button>查看该时点</button> <a href="/">查看全部</a></form>
<details><summary>录入一份材料</summary><form method="post" action="/import">{secret}
<label>材料编号 <input name="编号" required></label><label>披露时间 <input type="datetime-local" name="发布时间" required></label>
<label>发布来源 <input name="来源" required></label><label>正文 <textarea rows="4" name="正文" required></textarea></label>
<button>导入并查看最新时间线</button></form></details>
<details><summary>使用虚构样例</summary><form method="post" action="/examples">{secret}
<button>导入八份公开示例</button></form>
<form method="post" action="/link-examples">{secret}<button>导入多合同归并示例</button></form>
<form method="post" action="/evidence-examples">{secret}<button>导入澄清与金额更正示例</button></form>
<form method="post" action="/stage-three">{secret}<button>导入第三阶段双类型示例</button></form></details>"""

def make_server(db_path, port=0):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db_path)) as db:
        initialize(db)
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def parse_request(self):
            if not super().parse_request():
                return False
            if self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
                self.send_error(403)
                return False
            return True

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path != "/":
                return self.send_error(404)
            query = parse_qs(url.query)
            cutoff = query.get("until", [""])[0].replace("T", " ")
            try:
                cutoff = stamp(cutoff) if cutoff else ""
            except ValueError:
                return self.send_error(400, "Invalid date")
            with closing(sqlite3.connect(db_path)) as db:
                rows = records(db, cutoff)
            data = report(rows, cutoff, controls(token, cutoff, query.get("notice", [""])[0])).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path != "/import" and self.path not in EXAMPLES:
                return self.send_error(404)
            try:
                size = int(self.headers.get("Content-Length","0"))
            except ValueError:
                return self.send_error(400)
            if not 0 < size <= 1024*1024:
                return self.send_error(413)
            form = parse_qs(self.rfile.read(size).decode("utf-8", "replace"))
            if form.get("token") != [token]:
                return self.send_error(403)
            if self.path in EXAMPLES:
                rows = []
                for name in EXAMPLES[self.path]:
                    rows.extend(json.loads((ROOT/"data"/"examples"/name).read_text(encoding="utf-8-sig"))["材料"])
            else:
                row = {k: form.get(k, [""])[0] for k in ("编号","发布时间","来源","正文")}
                row["发布时间"] = row["发布时间"].replace("T"," ")
                rows = [row]
            with closing(sqlite3.connect(db_path)) as db:
                counts, errors = ingest(db, rows)
            msg = "，".join(f"{k} {v}" for k,v in counts.items())
            self.send_response(303)
            self.send_header("Location", "/?"+urlencode({"notice":"；".join([msg,*errors])}))
            self.end_headers()

    return HTTPServer(("127.0.0.1",port), Handler)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    with make_server(args.db,args.port) as server:
        url=f"http://127.0.0.1:{server.server_port}/"
        print(f"打开 {url} ，按 Ctrl+C 关闭。", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__=="__main__":
    main()
