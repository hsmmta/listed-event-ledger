from collections import Counter, defaultdict
from html import escape
from src.link.timeline import timelines
from app.dashboard import dashboard

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


def review_anchor(document):
    return "amount-" + document.encode().hex()


def amount_panel(row, token):
    task = row["金额复核"]
    edits = task["记录"]
    doc = row["编号"]
    anchor = quote_anchor(doc, task["起点"], task["终点"])
    status = "已复核" if edits else "待处理"
    parts = [f'<section id="{review_anchor(doc)}"><h4>合同金额复核 · {status}</h4>',
             f'<p>机器原值 {escape(task["机器原值"])}。原句含多个金额，请核对本次签约金额。</p>',
             f'<blockquote>{escape(task["原句"])}</blockquote><a href="#{anchor}">定位金额原句</a>']
    for edit in edits:
        parts.append(f'<p><strong>人工复核　{escape(edit["原值"])} → {escape(edit["新值"])}</strong><br>'
                     f'{escape(edit["处理时间"])} · {escape(edit["处理人"])} · {escape(edit["理由"])}</p>')
    if token:
        choices = "".join(f'<option>{escape(value)}</option>' for value in task["可选金额"])
        revision = edits[-1]["序号"] if edits else 0
        parts.append(f'<form method="post" action="/amount-review">'
                     f'<input type="hidden" name="token" value="{escape(token)}">'
                     f'<input type="hidden" name="document" value="{escape(doc)}">'
                     f'<input type="hidden" name="revision" value="{revision}">'
                     f'<label>核对后的合同金额 <select name="amount" required>'
                     f'<option value="">请选择原文金额</option>{choices}</select></label>'
                     '<label>处理人 <input name="reviewer" required maxlength="80"></label>'
                     '<label>处理理由 <input name="reason" required maxlength="1000"></label>'
                     '<button>保存复核记录</button></form>')
    return "".join(parts) + "</section>"


def entry(row, source_spans, candidate_ids, token=None):
    esc = escape
    info = " · ".join(row[k] for k in ("发布时间","编号","来源","材料性质"))
    parts = [f'<article id="doc-{row["编号"].encode().hex()}"><small>' + esc(info) + "</small>"]
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
    for finding in row["出处判断"]:
        if len(finding["报道链"]) == 1:
            continue
        parts.append("<p>" + esc(finding["动作"] + " · " + finding["说明"]) + "</p>")
        links = []
        for ref in finding["报道链"]:
            target = quote_anchor(ref["材料"], ref["起点"], ref["终点"])
            label = " · ".join(ref[k] for k in ("材料", "来源", "发布时间"))
            links.append(f'<a href="#{target}">{esc(label)}</a>')
        if links:
            parts.append("<p>此次为再传播，原报道披露于 " + esc(finding["报道链"][0]["发布时间"]) + "</p>")
            parts.append("<p>" + " → ".join(links) + "</p>")
    for link in row["核验"]:
        parts.append("<p><strong>" + esc(link["关系"]) + "</strong>　" + esc(link["说明"]) + "</p>")
        for ref in link["依据"]:
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
    if "金额复核" in row:
        task = row["金额复核"]
        spans[task["起点"], task["终点"]] = quote_anchor(row["编号"], task["起点"], task["终点"])
        parts.append(amount_panel(row, token))
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

def report(rows, cutoff, controls="", review_token=None, interactive=False):
    groups, pending = timelines(rows)
    tasks = [row for row in rows if "金额复核" in row]
    review_summary = f"{len(pending)} 份待复核"
    if tasks:
        remaining = sum(not row["金额复核"]["记录"] for row in tasks)
        review_summary = f"{len(pending)} 份归属待复核 · <a href='#amount-tasks'>{remaining} 条金额待处理</a>"
    summary = f"<p>披露截至 {escape(cutoff or '库内最新')} · {len(rows)} 份材料 · {len(groups)} 组事项候选 · {review_summary}</p>"
    parts = []
    source_spans = defaultdict(dict)
    candidate_ids = {}
    for row in rows:
        for ref in row["归并证据"]:
            start, end = ref["起点"], ref["终点"]
            source_spans[ref["材料"]][start, end] = quote_anchor(ref["材料"], start, end)
        if row["合同编号"] and row["事项编号"]:
            candidate_ids[row["公司"], row["对手"], row["合同编号"]] = row["事项编号"]
    if tasks:
        parts.append("<nav id='amount-tasks' aria-label='金额复核任务'><h2>合同金额复核任务</h2><ul>")
        for row in sorted(tasks, key=lambda r: bool(r["金额复核"]["记录"])):
            status = "已复核" if row["金额复核"]["记录"] else "待处理"
            label = " · ".join([row["公司"] or row["来源"], row["项目"], row["编号"], status])
            parts.append(f'<li><a href="#{review_anchor(row["编号"])}">{escape(label)}</a></li>')
        parts.append("</ul></nav>")
    if pending:
        parts.append('<a href="#review">查看待复核材料</a>')
    for matter_id, events in groups:
        first = events[0]
        company, party, project = first["公司"], first["对手"], first["项目"]
        title = f'{project} · 合同 {first["合同编号"]}' if first["合同编号"] else project
        parts.append(f'<section id="matter-{escape(matter_id)}"><h2>'+escape(title)+"</h2><p>"+escape(" · ".join(filter(None, (matter_id, company, party))))+f" · {len(events)} 份材料</p>")
        by_claim = defaultdict(list)
        for event in events:
            for finding in event["出处判断"]:
                by_claim[finding["动作"], finding["说法正文"]].append(finding)
        for (action, content), findings in by_claim.items():
            if not any(len(f["报道链"]) > 1 for f in findings):
                continue
            roots = {f["报道链"][0]["材料"] for f in findings if f["报道链"]}
            unknown = sum(not f["报道链"] for f in findings)
            docs = {f["本篇引句"]["材料"] for f in findings}
            parts.append(f"<p>{escape(content)}　{len(docs)} 份材料，{len(roots)} 条可追溯报道链，"
                         f"{unknown} 条说法出处待核。</p>")
        citations = Counter(r["引述来源"] for r in events if r["引述来源"] and
                            any(not f["报道链"] for f in r["出处判断"]))
        for source, count in citations.items():
            if count > 1:
                parts.append(f"<p>{count} 份转述均标注来自{escape(source)}，是否出自同一篇原稿待核。</p>")
        statements = [r for r in events if r["材料性质"]=="公告披露"]
        if statements:
            last = statements[-1]
            parts.append("<p>最近公告所述（"+escape(last["编号"])+"）："+escape("、".join(dict.fromkeys(c["动作"] for c in last["说法"])))+"</p>")
        else:
            parts.append("<p>当前可见材料中仅有报道或转述。</p>")
        if first.get("事件类型") == "业绩":
            for event in events:
                value = event["业绩值"]
                amount = value["下限"] if value["上限"] == value["下限"] else value["下限"] + " 至 " + value["上限"]
                claim = event["说法"][0]
                target = quote_anchor(event["编号"], claim["起点"], claim["终点"])
                label = event["发布时间"] + " · " + event["编号"]
                parts.append(f'<p>{escape(value["阶段"] + "　" + amount + value["单位"])}　'
                             f'<a href="#{target}">{escape(label)}</a></p>')
        parts.append("<h3>披露时间线</h3>")
        parts.extend(entry(r, source_spans, candidate_ids, review_token) for r in events)
        parts.append("</section>")
    if pending:
        parts.append('<section id="review"><h2>待复核材料</h2>')
        parts.extend(entry(r, source_spans, candidate_ids, review_token) for r in pending)
        parts.append("</section>")
    if interactive:
        return dashboard(rows, groups, pending, tasks, cutoff, controls, "\n".join(parts), summary)
    prefix = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>上市公司事项追踪</title><style>"+STYLE+"</style><h1>上市公司事项追踪</h1>", controls, summary]
    return "\n".join(prefix + parts)+"</html>"
