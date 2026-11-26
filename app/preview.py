from collections import Counter, defaultdict
from html import escape
from src.link.timeline import timelines

STYLE = """
:root{font-family:system-ui,sans-serif;color:#183347;background:#f4f6f7}
body{max-width:980px;margin:2rem auto;padding:0 1rem;line-height:1.65}
section,form{background:white;padding:1rem 1.3rem;border-radius:.6rem;margin:1rem 0}
article{border-top:1px solid #d9e0e3;padding:.7rem 0}small{color:#475e69}
blockquote{border-left:3px solid #32786f;margin:.4rem 0;padding:0 1rem}
.source-text{white-space:pre-wrap}mark{background:transparent}mark:target{background:#ffdf80;outline:2px solid #805600}
summary,button{cursor:pointer}label{display:block;margin:.5rem 0}
input,textarea,button{font:inherit;padding:.3rem}textarea{width:95%}
"""
def quote_anchor(doc, start, end):
    return f"quote-{doc.encode('utf-8').hex()}-{start}-{end}"


def entry(row, source_spans, candidate_ids):
    esc = escape
    info = " · ".join(row[k] for k in ("发布时间","编号","来源","材料性质"))
    parts = ["<article><small>" + esc(info) + "</small>"]
    if row["引述来源"]:
        parts.append("<p>文中引述 " + esc(row["引述来源"]) + "</p>")
    if row["待复核"]:
        parts.append("<p>待复核：" + esc("、".join(row["待复核"])) + "</p>")
    body = row["正文"]
    spans = dict(source_spans[row["编号"]])
    if row["归并依据"]:
        parts.append("<p>归并依据：" + esc(row["归并依据"]) + "</p>")
    if row["候选合同编号"]:
        links = []
        for code in row["候选合同编号"]:
            target = candidate_ids[row["公司"], row["对手"], code]
            links.append(f'<a href="#matter-{target}">{esc(code)}</a>')
        parts.append("<p>候选合同：" + "、".join(links) + "</p>")
    for ref in row["归并证据"]:
        anchor = quote_anchor(ref["材料"], ref["起点"], ref["终点"])
        label = " · ".join(ref[k] for k in ("材料", "来源", "发布时间"))
        parts.append(f'<p><a href="#{anchor}">{esc(label)}</a>　{esc(ref["引句"])}</p>')
    for claim in row["说法"]:
        parts.append("<strong>"+esc(claim["动作"])+"</strong><blockquote>"+esc(claim["原句"])+"</blockquote>")
        start, end = claim["起点"], claim["终点"]
        if 0 <= start < end <= len(body) and body[start:end] == claim["原句"]:
            anchor = quote_anchor(row["编号"], start, end)
            spans[start, end] = anchor
            parts.append(f'<a href="#{anchor}">定位原文（第 {start + 1} 至 {end} 字）</a>')
    for amount in row["金额"]:
        parts.append("<p>"+esc(amount["原文角色"]+" "+amount["数值"]+amount["单位"])+"</p>")
    parts.append('<details><summary>查看材料全文</summary><p class="source-text">')
    cursor = 0
    for (start, end), anchor in sorted(spans.items()):
        parts.extend([esc(body[cursor:start]), f'<mark id="{anchor}">',
                      esc(body[start:end]), "</mark>"])
        cursor = end
    parts.append(esc(body[cursor:]) + "</p></details></article>")
    return "".join(parts)

def report(rows, cutoff, controls=""):
    groups, pending = timelines(rows)
    parts = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>合同事项追踪</title><style>"+STYLE+"</style><h1>合同事项追踪</h1>", controls,
             f"<p>披露截至 {escape(cutoff or '库内最新')} · {len(rows)} 份材料 · {len(groups)} 组事项候选 · {len(pending)} 份待复核</p>"]
    source_spans = defaultdict(dict)
    candidate_ids = {}
    for row in rows:
        for ref in row["归并证据"]:
            start, end = ref["起点"], ref["终点"]
            source_spans[ref["材料"]][start, end] = quote_anchor(ref["材料"], start, end)
        if row["合同编号"] and row["事项编号"]:
            candidate_ids[row["公司"], row["对手"], row["合同编号"]] = row["事项编号"]
    if pending:
        parts.append('<a href="#review">查看待复核材料</a>')
    for matter_id, events in groups:
        first = events[0]
        company, party, project = first["公司"], first["对手"], first["项目"]
        title = f'{project} · 合同 {first["合同编号"]}' if first["合同编号"] else project
        parts.append(f'<section id="matter-{escape(matter_id)}"><h2>'+escape(title)+"</h2><p>"+escape(matter_id+" · "+company+" · "+party)+f" · {len(events)} 份材料</p>")
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
        parts.append("<h3>披露时间线</h3>")
        parts.extend(entry(r, source_spans, candidate_ids) for r in events)
        parts.append("</section>")
    if pending:
        parts.append('<section id="review"><h2>待复核材料</h2>')
        parts.extend(entry(r, source_spans, candidate_ids) for r in pending)
        parts.append("</section>")
    return "\n".join(parts)+"</html>"
