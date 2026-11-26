from html import escape

def report(rows, cutoff):
    parts=["<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>合同事项追踪</title><style>body{max-width:880px;margin:3em auto;padding:0 1.5em;font:16px/1.7 system-ui;color:#24384a}article{border-top:1px solid #b8c9d4;padding:1em 0}small{color:#526576}summary{cursor:pointer}blockquote{margin-left:1em;border-left:3px solid #53877c;padding-left:1em}</style><h1>合同事项追踪</h1>",
           f"<p>披露时间截至 {escape(cutoff or '库内最新')} · {len(rows)} 份材料 · 本地规则抽取</p>"]
    for r in rows:
        title=" · ".join(r[k] or "待核" for k in ("公司","对手","项目"))
        parts.extend([f"<article><small>{escape(r['发布时间'])}　{escape(r['编号'])}　{escape(r['来源'])}</small><h2>{escape(title)}</h2>",
                      f"<p>{escape(r['材料性质'])}　{escape(r['引述来源'])}</p>"])
        if r["待复核"]:
            parts.append("<strong>待复核："+escape("、".join(r["待复核"]))+"</strong>")
        for c in r["说法"]:
            parts.append(f"<p>{escape(c['动作'])}</p><blockquote>{escape(c['原句'])}</blockquote>")
        for a in r["金额"]:
            parts.append("<p>"+escape(a["原文角色"]+" "+a["数值"]+a["单位"])+"</p>")
        parts.append("<details><summary>查看材料全文</summary><p>"+escape(r["正文"])+"</p></details></article>")
    return "\n".join(parts)+"</html>"
