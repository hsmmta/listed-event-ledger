"""在空库回放八份虚构合同材料，对照预标注统计最终截面的归并结果。"""
from contextlib import closing
from itertools import combinations
import json
from pathlib import Path
import sqlite3

from src.common.storage import initialize, records
from src.ingest.materials import ingest


ROOT = Path(__file__).resolve().parents[1]


def compare(expected, actual):
    if expected.keys() != actual.keys():
        raise ValueError("参考答案与实际输出的材料编号不一致")
    known = [doc for doc, label in expected.items() if label is not None]
    pairs = {"正确同组": [], "正确分开": [], "错并": [], "漏并": [], "未决": []}
    for left, right in combinations(known, 2):
        same_contract = expected[left] == expected[right]
        if actual[left] is None or actual[right] is None:
            result = "未决"
        elif actual[left] == actual[right]:
            result = "正确同组" if same_contract else "错并"
        else:
            result = "漏并" if same_contract else "正确分开"
        pairs[result].append(f"{left}/{right}")
    return pairs


def main():
    materials = json.loads((ROOT / "data/examples/B01-B08.json").read_text(encoding="utf-8"))["材料"]
    labels = json.loads((ROOT / "eval/expected/多合同归并.json").read_text(encoding="utf-8"))["标注"]
    expected = {doc: item["归属"] for doc, item in labels.items()}
    with closing(sqlite3.connect(":memory:")) as db:
        initialize(db)
        counts, errors = ingest(db, materials)
        if errors or counts["新增"] != len(materials):
            raise ValueError(f"导入结果与样例规模不符：{counts} {errors}")
        rows = records(db, max(row["发布时间"] for row in materials))

    actual = {row["编号"]: row["事项编号"] for row in rows}
    pairs = compare(expected, actual)
    print("## 逐份核对\n")
    print("| 材料 | 预期事项 | 实际事项 | 预标注依据 |")
    print("|---|---|---|---|")
    for doc, item in labels.items():
        print(f'| {doc} | {item["归属"] or "待核"} | {actual[doc] or "待核"} | {item["理由"]} |')

    print("\n## 已知归属的材料对\n")
    for result, members in pairs.items():
        print(f'- {result} {len(members)} 对：{"、".join(members) or "无"}')
    print("\n## 逐份统计待核\n")
    expected_pending = {doc for doc in expected if expected[doc] is None}
    actual_pending = {doc for doc in actual if actual[doc] is None}
    for name, members in (("预期应待核", expected_pending), ("系统实际待核", actual_pending),
                          ("应待核却已归组", expected_pending - actual_pending),
                          ("可判定却被留待核", actual_pending - expected_pending)):
        print(f'- {name} {len(members)} 份：{"、".join(sorted(members)) or "无"}')


if __name__ == "__main__":
    main()
