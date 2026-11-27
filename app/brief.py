"""从两个历史截面生成可离线核查的公司简报。"""
from collections import defaultdict
from datetime import datetime
from html import escape

from app.preview import STYLE
from src.common.storage import records


def brief_form(rows, cutoff):
    companies = sorted({r["公司"] for r in rows if r["公司"]})
    if not companies:
        return ""
    options = "".join(f'<option>{escape(company)}</option>' for company in companies)
    end = cutoff or max(rows[-1]["发布时间"], datetime.now().strftime("%Y-%m-%d %H:%M"))
    start = rows[0]["发布时间"][:10] + "T00:00"
    return f"""<details><summary>公司研究简报</summary><form action="/brief" method="get">
<label>公司 <select name="company">{options}</select></label>
<label>比较起点 <input required type="datetime-local" name="start" value="{start}"></label>
<label>截至时点 <input required type="datetime-local" name="end" value="{end.replace(' ', 'T')}"></label>
<button>查看简报</button> <button name="download" value="1">下载 HTML 简报</button>
</form></details>"""


def judgment(row):
    actions = list(dict.fromkeys(c["动作"] for c in row["说法"]))
    value = row.get("业绩值")
    if value:
        bounds = list(dict.fromkeys([value["下限"], value["上限"]]))
        return value["阶段"] + " " + " 至 ".join(bounds) + value["单位"]
    result = actions or ["披露内容待核"]
    for a in row["金额"]:
        result.append(a["原文角色"] + " " + a["数值"] + a["单位"])
    task = row.get("金额复核")
    if task and not task["记录"]:
        result.append("机器抽取，金额待核")
    return "，".join(result)


def section(title, lines, empty):
    items = "".join("<li>" + line + "</li>" for line in lines)
    return f"<section><h2>{title}</h2>" + (f"<ul>{items}</ul>" if items else f"<p>{empty}</p>") + "</section>"


def brief(db, company, start, end):
    earlier = {r["编号"]: r for r in records(db, start) if r["公司"] == company}
    rows = [r for r in records(db, end) if r["公司"] == company]
    changes, pending, current = [], [], []
    groups = defaultdict(list)
    sources = {}

    def cite(row):
        doc = row["编号"]
        sources[doc] = row
        return f'<a href="#doc-{doc.encode().hex()}">{escape(doc)}</a>'

    index = {r["编号"]: r for r in rows}
    for row in rows:
        doc = row["编号"]
        ref = cite(row)
        old = earlier.get(doc)
        if row["事项编号"]:
            groups[row["事项编号"]].append(row)
        if not old:
            changes.append(f'{row["发布时间"]} · {escape(row["材料性质"])} · {escape(judgment(row))} {ref}')
        elif old["事项编号"] != row["事项编号"]:
            changes.append(f'事项归属更新 · {escape(old["事项编号"] or "待核")} → '
                           f'{escape(row["事项编号"] or "待核")} {ref}')
        for relation in row["核验"]:
            if old and relation in old["核验"]:
                continue
            kind = relation["关系"]
            title = "公司更正披露" if kind == "金额更正" else kind
            evidence = "、".join(cite(index[r["材料"]]) for r in relation["依据"] if r["材料"] in index)
            changes.append(f'{row["发布时间"]} · {escape(title)} · {escape(relation["说明"])} {evidence}')
        problems = list(row["待复核"])
        for finding in row["出处判断"]:
            if not finding["报道链"]:
                problems.append(finding["说明"])
            elif not old and len(finding["报道链"]) > 1:
                origin = finding["报道链"][0]["材料"]
                if origin in index:
                    changes.append(f'转载所引原稿 {cite(index[origin])}，本次转述 {ref}')
        task = row.get("金额复核")
        if task:
            if not task["记录"]:
                problems.append("同句出现多个金额，合同金额待核")
            for edit in task["记录"]:
                if edit["处理时间"][:16] > start:
                    changes.append(escape(f'{edit["处理时间"]} · 研究者修正抽取 · {edit["原值"]} → '
                                          f'{edit["新值"]} · {edit["处理人"]} · {edit["理由"]}') + " " + ref)
        if problems:
            pending.append(escape("、".join(dict.fromkeys(problems))) + " " + ref)
    old_groups = defaultdict(list)
    for row in earlier.values():
        if row["事项编号"]:
            old_groups[row["事项编号"]].append(row)
    for matter, events in groups.items():
        official = [r for r in events if r["材料性质"] == "公告披露"]
        row = (official or events)[-1]
        label = "最近公告所述" if official else "仅见报道或转述"
        title = " · ".join(filter(None, [row["项目"], row["合同编号"]]))
        previous = old_groups.get(matter, [])
        if previous:
            prior = next((r for r in reversed(previous) if r["材料性质"] == "公告披露"), previous[-1])
            if judgment(prior) != judgment(row) and prior["编号"] in index:
                changes.append(f'{escape(title)} · 起点 {escape(judgment(prior))} {cite(index[prior["编号"]])}'
                               f' → 期末 {escape(judgment(row))} {cite(row)}')
        summary = f'<strong>{escape(title)}</strong>　{label} · {escape(judgment(row))} {cite(row)}'
        edits = row.get("金额复核", {}).get("记录", [])
        if edits:
            last = edits[-1]
            summary += "（" + escape(f'研究者复核于 {last["处理时间"]}，{last["处理人"]}，'
                                    f'{last["原值"]} → {last["新值"]}，{last["理由"]}') + "）"
        current.append(summary)
    evidence = []
    for doc, row in sources.items():
        evidence.append(f'<article id="doc-{doc.encode().hex()}"><strong>{escape(doc)}</strong> · '
                        f'{escape(row["来源"])} · 披露于 {row["发布时间"]}'
                        f'<blockquote class="source-text">{escape(row["正文"])}</blockquote></article>')
    return (f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" '
            f'content="width=device-width, initial-scale=1"><title>{escape(company)}研究简报</title><style>{STYLE}'
            'li{margin:.45em 0}article:target{background:#fff4c2}@media print{section{padding:0}article{break-inside:avoid}}'
            f'</style><h1>{escape(company)}研究简报</h1><p>{start} 至 {end}（本地时间，起点之后至终点）</p>'
            + section("期间变化", changes, "期间未发现新增披露或判断变化。")
            + section("截至期末的判断", current, "截至此时暂无可归属的事项。")
            + section("仍需核查", pending, "当前可见材料中没有已标记的待核问题。")
            + "<section><h2>材料原文与出处</h2>" + ("".join(evidence) or "<p>截至此时无该公司材料。</p>")
            + "</section></html>")
