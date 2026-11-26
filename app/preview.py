from collections import Counter
from html import escape
from src.link.timeline import timelines

STYLE = """
:root{font-family:system-ui,sans-serif;color:#183347;background:#f4f6f7}
body{max-width:980px;margin:2rem auto;padding:0 1rem;line-height:1.65}
section,form{background:white;padding:1rem 1.3rem;border-radius:.6rem;margin:1rem 0}
article{border-top:1px solid #d9e0e3;padding:.7rem 0}small{color:#475e69}
blockquote{border-left:3px solid #32786f;margin:.4rem 0;padding:0 1rem}
summary,button{cursor:pointer}label{display:block;margin:.5rem 0}
input,textarea,button{font:inherit;padding:.3rem}textarea{width:95%}
"""
def entry(row):
    esc = escape
    info = " · ".join(row[k] for k in ("发布时间","编号","来源","材料性质"))
    parts = ["<article><small>" + esc(info) + "</small>"]
    if row["引述来源"]:
        parts.append("<p>文中引述 " + esc(row["引述来源"]) + "</p>")
    if row["待复核"]:
        parts.append("<p>待复核：" + esc("、".join(row["待复核"])) + "</p>")
    for claim in row["说法"]:
        parts.append("<strong>"+esc(claim["动作"])+"</strong><blockquote>"+esc(claim["原句"])+"</blockquote>")
    for amount in row["金额"]:
        parts.append("<p>"+esc(amount["原文角色"]+" "+amount["数值"]+amount["单位"])+"</p>")
    parts.append("<details><summary>查看材料全文</summary><p>"+esc(row["正文"])+"</p></details></article>")
    return "".join(parts)

def report(rows, cutoff, controls=""):
    groups, pending = timelines(rows)
    parts = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>合同事项追踪</title><style>"+STYLE+"</style><h1>合同事项追踪</h1>", controls,
             f"<p>披露截至 {escape(cutoff or '库内最新')} · {len(rows)} 份材料 · {len(groups)} 组事项候选 · {len(pending)} 份待复核</p>"]
    for (company,party,project), events in groups:
        parts.append("<section><h2>"+escape(project)+"</h2><p>"+escape(company+" · "+party)+f" · {len(events)} 份材料</p>")
        citations = Counter(r["引述来源"] for r in events if r["引述来源"])
        for source, count in citations.items():
            if count > 1:
                parts.append(f"<p>{count} 份转述均标注来自{escape(source)}，是否出自同一篇原稿待核。</p>")
        statements = [r for r in events if r["材料性质"]=="公告披露"]
        if statements:
            last = statements[-1]
            parts.append("<p>最近公告所述（"+escape(last["编号"])+"）："+escape("、".join(dict.fromkeys(c["动作"] for c in last["说法"])))+"</p>")
        else:
            parts.append("<p>当前可见材料中仅有报道或转述。</p>")
        parts.extend(entry(r) for r in events)
        parts.append("</section>")
    if pending:
        parts.append("<section><h2>待复核材料</h2>")
        parts.extend(entry(r) for r in pending)
        parts.append("</section>")
    return "\n".join(parts)+"</html>"
