"""按已抽取的三个字段生成可回放的合同事项候选。"""

def timelines(rows):
    groups = {}
    pending = []
    for row in sorted(rows, key=lambda r: (r["发布时间"], r["编号"])):
        key = tuple(row[k] for k in ("公司", "对手", "项目"))
        if not all(key) or row["待复核"]:
            pending.append(row)
            continue
        groups.setdefault(key, []).append(row)
    return sorted(groups.items(), key=lambda item: item[1][-1]["发布时间"], reverse=True), pending
