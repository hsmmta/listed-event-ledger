"""按已保存的事项编号重建当前截面的时间线。"""

def timelines(rows):
    groups = {}
    pending = []
    for row in sorted(rows, key=lambda r: (r["发布时间"], r["编号"])):
        key = row["事项编号"]
        if key is None:
            pending.append(row)
            continue
        groups.setdefault(key, []).append(row)
    return sorted(groups.items(), key=lambda item: item[1][-1]["发布时间"], reverse=True), pending
