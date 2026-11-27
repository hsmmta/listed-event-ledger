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
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from app.brief import brief, brief_form

from app.preview import report, review_anchor
from src.common.storage import initialize, records, stamp
from src.ingest.materials import ingest
from src.verify.amount_review import DEFAULT_DB, correct_amount

ROOT = Path(__file__).resolve().parents[1]

EXAMPLES = {
    "/trial-examples": ("F01-F03.json",),
    "/review-example": ("R01-金额复核.json",),
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
<form method="post" action="/trial-examples">{secret}<button>导入第四阶段试用示例</button></form>
<form method="post" action="/review-example">{secret}<button>导入人工金额复核示例</button></form>
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
            if url.path == "/brief":
                return self.show_brief(parse_qs(url.query))
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
            data = report(rows, cutoff, controls(token, cutoff, query.get("notice", [""])[0]) + brief_form(rows, cutoff),
                          review_token=None if cutoff else token).encode()
            self.html_response(data)

        def show_brief(self, query):
            company = query.get("company", [""])[0].strip()
            try:
                start, end = (stamp(query[key][0].replace("T", " ")) for key in ("start", "end"))
                if not company or start > end:
                    raise ValueError
            except (KeyError, ValueError):
                return self.html_response("<p>请选择公司及有效时点，比较起点须早于或等于截至时点。</p>".encode(), 400)
            with closing(sqlite3.connect(db_path)) as db:
                db.execute("BEGIN")
                data = brief(db, company, start, end).encode()
            name = f"{company}-研究简报-{end[:10]}.html" if query.get("download") == ["1"] else ""
            self.html_response(data, filename=name)

        def html_response(self, data, status=200, filename=""):
            self.send_response(status)
            if filename:
                self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(filename, safe=""))
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            if self.path not in ("/import", "/amount-review") and self.path not in EXAMPLES:
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
            if self.path == "/amount-review":
                doc = form.get("document", [""])[0]
                try:
                    revision = int(form.get("revision", ["-1"])[0])
                    with closing(sqlite3.connect(db_path)) as db:
                        correct_amount(db, doc, revision, form.get("amount", [""])[0],
                                       form.get("reviewer", [""])[0], form.get("reason", [""])[0])
                    message = "已保存人工金额复核"
                except ValueError as exc:
                    message = f"未保存：{exc}"
                    self.redirect(message)
                    return
                self.redirect(message, "#" + review_anchor(doc))
                return
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
            self.redirect("；".join([msg, *errors]))

        def redirect(self, message, fragment=""):
            self.send_response(303)
            self.send_header("Location", "/?" + urlencode({"notice": message}) + fragment)
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
