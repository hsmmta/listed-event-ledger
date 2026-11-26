"""用一个披露截面内的材料解释合同归属，不改写入库时的原文或基础分组。"""
from collections import defaultdict
from hashlib import sha256
import json
import re


NUMBER = re.compile(
    r"(?:^|(?<=[，,。；;\n]))[ \t]*(?:本)?合同编号\s*(?:为|是)?\s*[:：]?\s*"
    r"([A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)*)[ \t]*(?=$|[，,。；;\n])"
)
MISSING = re.compile(r"(?:尚未取得|未取得|未提供|未披露|未注明)合同编号")
NAME = r'[“"]([^“”"。；\n]{1,40})[”"]'
ALIAS = re.compile(
    r'(?:^|(?<=[，,。；;\n]))\s*' + NAME
    + r'\s*(即|为|(?:[（(]\s*)?(?:以下)?简称(?:为)?)\s*' + NAME
    + r'(的简称|[）)])?\s*(?=$|[。；，,;\n])'
)
UNCERTAIN = re.compile(r"(?:无法|不能|尚难)(?:确定|确认|区分)(?:其|具体|对应|所属)*(?:批次|合同|项目)")
SENTENCE = re.compile(r"[^。！？；\n]+[。！？；]?")


def stable_id(scope, kind, value):
    key = json.dumps([*scope, kind, value], ensure_ascii=False).encode()
    return "K-" + sha256(key).hexdigest()[:20]


def evidence(row, match):
    for sentence in SENTENCE.finditer(row["正文"]):
        if sentence.start() <= match.start(1) < sentence.end():
            return {"材料": row["编号"], "来源": row["来源"], "发布时间": row["发布时间"],
                    "引句": sentence.group(), "起点": sentence.start(), "终点": sentence.end()}
    raise ValueError("归并引句超出正文范围")


def number_field(row):
    body = row["正文"]
    matches = list(NUMBER.finditer(body))
    numbers = {m[1] for m in matches}
    mentions = MISSING.sub("", body).count("合同编号")
    if not mentions:
        return "", None, ""
    if len(matches) != mentions or len(numbers) != 1 or not re.search(r"\d", matches[0][1]):
        return "", None, "合同编号的指代、数量或格式不明确"
    return matches[0][1], evidence(row, matches[0]), ""


def add_evidence(row, ref):
    if ref not in row["归并证据"]:
        row["归并证据"].append(ref)


def resolve_scope(scope, rows):
    by_name = defaultdict(dict)   # 每个项目名下，每个编号最早可见的原句
    aliases = defaultdict(dict)   # 简称 -> 全称 -> 声明出处
    base_ids = {}
    ready = []
    for row in rows:
        name = row["项目"]
        number, ref, issue = number_field(row)
        if issue:
            row["待复核"].append(issue)
            row["事项编号"] = None
            continue
        base_ids[name] = row["事项编号"]
        if number:
            row["合同编号"] = number
            by_name[name].setdefault(number, ref)
            add_evidence(row, ref)
        for match in ALIAS.finditer(row["正文"]):
            left, relation, right, suffix = match.groups()
            if (relation == "为") != (suffix == "的简称"):
                continue
            if name in (left, right) and left != right:
                short, full = (left, right) if relation in ("即", "为") else (right, left)
                aliases[short].setdefault(full, evidence(row, match))
        ready.append(row)

    # 同一个简称指向不同全称时，不用它在两个项目之间传递编号。
    equivalent = defaultdict(dict)
    for short, targets in aliases.items():
        for full, ref in targets.items():
            equivalent[short][full] = ref
            if len(targets) == 1:
                equivalent[full][short] = ref

    for row in ready:
        name = row["项目"]
        number = row["合同编号"]
        if number:
            row["归并依据"] = "原文列明合同编号，连同公司和交易对手确定归属"
        else:
            options = dict(by_name[name])
            for other, ref in equivalent[name].items():
                add_evidence(row, ref)
                for candidate, source in by_name[other].items():
                    options.setdefault(candidate, source)
            for source in options.values():
                add_evidence(row, source)
            if len(options) > 1 or len(aliases.get(name, {})) > 1 or UNCERTAIN.search(row["正文"]):
                row["事项编号"] = None
                row["候选合同编号"] = sorted(options)
                reason = "可见材料不足以唯一确定合同归属"
                if len(aliases.get(name, {})) > 1:
                    reason += "，该简称对应：" + "、".join(sorted(aliases[name]))
                row["待复核"].append(reason)
                continue
            if options:
                number = next(iter(options))
                row["合同编号"] = number
                row["归并依据"] = "按当前截面的公司、对手及项目名称匹配唯一已披露编号"
                if equivalent[name]:
                    row["归并依据"] += "，项目别名见引句"
            elif aliases.get(name):
                full = next(iter(aliases[name]))
                row["事项编号"] = base_ids.get(full) or stable_id(scope, "项目", full)
                row["归并依据"] = "依据材料中的显式别名对应，暂列同一项目"
            else:
                row["归并依据"] = "公司、交易对手及项目全名相同，按名称暂列候选"
        if number:
            row["事项编号"] = stable_id(scope, "合同", number)


def resolve(rows):
    scopes = defaultdict(list)
    for row in rows:
        row.update(合同编号="", 候选合同编号=[], 归并证据=[], 归并依据="")
        if row["事项编号"] is not None and not row["待复核"]:
            scopes[row["公司"], row["对手"]].append(row)
    for scope, material in scopes.items():
        resolve_scope(scope, material)
    return rows
