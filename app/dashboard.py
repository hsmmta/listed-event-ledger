"""本机研究工作台的导航、事项索引与披露概览。"""
from collections import Counter
from datetime import date, timedelta
from html import escape
from pathlib import Path


ASSETS = Path(__file__).with_name("frontend")


def disclosure_chart(rows, day):
    counts = Counter(r["发布时间"][:10] for r in rows)
    days = [(day - timedelta(days=i)).isoformat() for i in reversed(range(min(14, day.toordinal())))]
    peak = max(1, *(counts[d] for d in days))
    bars = "".join(f'<i title="{d} · {counts[d]} 份" style="height:{max(3, counts[d]*100/peak):.2f}%"></i>' for d in days)
    return (f'<div class="chart"><small>最近 14 天披露量</small><div class="bars">{bars}</div>'
            f'<div class="axis"><span>{days[0][5:]}</span><span>{days[-1][5:]}</span></div></div>')


def dashboard(rows, groups, pending, tasks, cutoff, tools, evidence, summary):
    titles = {"home":"研究总览", "queue":"复核中心", "imports":"材料录入", "briefs":"研究简报", "history":"历史回看"}
    symbols = ["▦", "◉", "⊞", "▤", "◷"]
    nav = "".join(f'<a href="#{key}"><b aria-hidden="true">{icon}</b>{label}</a>'
                  for (key,label), icon in zip(titles.items(), symbols))
    latest = rows[-1]["发布时间"] if rows else ""
    end = date.fromisoformat((cutoff or latest)[:10]) if cutoff or latest else date.today()
    remaining = len(pending) + sum(not r["金额复核"]["记录"] for r in tasks)
    metrics = [(len({r["公司"] for r in rows if r["公司"]}), "跟踪公司"), (len(groups), "跟踪事项"),
               (len(rows), "材料总数"), (remaining, "待核任务")]
    stats = "".join(f'<div><strong>{n}</strong><small>{label}</small></div>' for n,label in metrics)
    items = []
    for key, events in groups:
        r = events[-1]
        kind = r.get("事件类型") or "合同"
        items.append(f'<a class="item" data-kind="{escape(kind)}" href="#matter-{escape(key)}">'
                     f'<span class="tag">{escape(kind)}</span><span class="item-title"><strong>{escape(r["项目"])}</strong>'
                     f'<small>{escape(r["公司"])} · {escape(r["合同编号"] or r["对手"] or kind)}</small></span>'
                     f'<span class="item-date">{escape(r["发布时间"][:10])}<small>{len(events)} 份材料</small></span><b>›</b></a>')
    feed = []
    for r in reversed(rows[-6:]):
        feed.append(f'<a class="feed-row" href="#doc-{r["编号"].encode().hex()}"><time>{r["发布时间"][5:16]}</time>'
                    f'<strong>{escape(r["公司"] or r["来源"])}</strong>'
                    f'<span>{escape(r["材料性质"])} · {escape(r["编号"])}</span></a>')
    queue = [] if tasks or pending else ["<p>当前截面没有待核任务。</p>"]
    style = (ASSETS / "workbench.css").read_text(encoding="utf-8")
    script = (ASSETS / "workbench.js").read_text(encoding="utf-8")
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>上市事项研究台</title><style>{style}</style></head><body>
<aside><div class="brand"><i aria-hidden="true">≋</i>上市事项研究台</div><nav aria-label="工作台导航">{nav}</nav>
<footer><span class="lamp"></span>本机工作库 <small>V4.3</small></footer></aside>
<main><header><span>研究工作台　/　<b id="breadcrumb">研究总览</b></span><a class="cta" href="#imports">＋ 录入材料</a></header>
{tools}<div id="home" data-view><div class="heading"><h1>研究总览</h1><small>{'历史截面　'+escape(cutoff) if cutoff else '最近披露　'+escape(latest or '暂无')}</small></div>
<div class="hero"><div class="stats">{stats}</div>{disclosure_chart(rows,end)}</div>
<div class="columns"><section class="box"><h2>事项追踪</h2><input id="search" type="search" aria-label="搜索公司、项目或合同编号" placeholder="搜索公司、项目或合同编号">
<div class="filters" aria-label="事件类型"><button aria-pressed="true">全部</button><button aria-pressed="false">合同</button><button aria-pressed="false">业绩</button></div>
<div id="items">{''.join(items)}</div><p id="empty" {'hidden' if items else ''}>{'没有匹配的事项' if rows else '工作库为空，可从材料录入开始。'}</p></section>
<section class="box feed"><h2>最近披露</h2>{''.join(feed) or '<p>暂无披露材料。</p>'}</section></div></div>
<section id="queue" data-view class="box"><h1>复核中心</h1>{summary}{''.join(queue)}</section>
{evidence}
</main><script>{script}</script></body></html>"""
