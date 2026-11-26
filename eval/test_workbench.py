from contextlib import redirect_stderr
import io
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler

from app.local import make_server

class WorkbenchTest(unittest.TestCase):
    def test_import_replay_and_restart(self):
        with TemporaryDirectory() as tmp, redirect_stderr(io.StringIO()):
            urlopen = build_opener(ProxyHandler({})).open
            db = Path(tmp)/"store.sqlite3"
            with make_server(db) as server:
                thread = Thread(target=server.serve_forever, daemon=True)
                thread.start()
                url=f"http://127.0.0.1:{server.server_port}"
                def read(path, form=None):
                    with urlopen(url+path, data=urlencode(form).encode() if form else None, timeout=5) as res:
                        return res.read().decode()
                try:
                    token=re.search(r'name="token" value="([^"]+)"',read("/")).group(1)
                    page=read("/examples", {"token":token})
                    self.assertIn("3 组事项候选 · 1 份待复核",page)
                    self.assertIn("2 份转述均标注来自行业简报甲",page)
                    self.assertIn("重复 8",read("/examples", {"token":token}))
                    row={"token":token,"编号":"T1","发布时间":"2026-11-09T17:00",
                         "来源":"丁公司公告","正文":"公司于11月8日与星湾集团签订光纤改造项目合同，金额为300万元。"}
                    page=read("/import", row)
                    self.assertIn("新增 1",page)
                    self.assertIn("<h2>光纤改造</h2>",page)
                    self.assertIn("4 组事项候选",page)
                    self.assertIn("失败 1",read("/import",dict(row,正文="其他正文")))
                    past=read("/?"+urlencode({"until":"2026-11-04T15:00"}))
                    self.assertNotIn("1200万元",past)
                    self.assertNotIn("光纤改造",past)
                    self.assertIn("800万元",past)
                    self.assertIn("最近公告所述（D3）",past)
                    linked = read("/link-examples", {"token": token})
                    self.assertIn("新增 8", linked)
                    self.assertIn('href="#review"', linked)
                    self.assertIn('>HT-02</a>', linked)
                    self.assertIn('北港仓储 · 合同 HT-02', linked)
                    self.assertIn('归并依据', linked)
                    for fragment in re.findall(r'href="#([^"]+)"', linked):
                        self.assertEqual(linked.count(f'id="{fragment}"'), 1, fragment)
                    cutoff = read("/?" + urlencode({"until": "2026-11-11T23:59"}))
                    self.assertNotIn("HT-02", cutoff)
                finally:
                    server.shutdown()
                    thread.join()
            with make_server(db) as reopened:
                thread=Thread(target=reopened.handle_request)
                thread.start()
                with urlopen(f"http://127.0.0.1:{reopened.server_port}/",timeout=5) as response:
                    self.assertIn("光纤改造",response.read().decode())
                thread.join()
