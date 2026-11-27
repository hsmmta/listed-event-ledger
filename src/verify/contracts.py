"""在当前可见材料中匹配合同说法及明确指向原公告的金额更正。"""
from collections import defaultdict
from datetime import date
import re

from src.link.resolve import number_field


DATE = r"\d{4}年\d{1,2}月\d{1,2}日"
SIGN_DATE = re.compile(r"于(" + DATE + r")与[^，。；]{1,40}?签(?:署|订)")
CORRECTION = re.compile(
    r"(?:本)?公司更正(?P<date>" + DATE + r")公告[：:]\s*合同编号(?:为|是|[:：])?\s*"
    r"(?P<number>[A-Za-z0-9][A-Za-z0-9/_-]*)的合同金额由"
    r"(?P<old>[\d]+(?:\.\d+)?(?:亿元|万元|元))更正为"
    r"(?P<new>[\d]+(?:\.\d+)?(?:亿元|万元|元))[。]?"
)
AMOUNT = re.compile(r"合同金额(?:约为|为|约|达)?\s*(\d+(?:\.\d+)?)\s*(亿元|万元|元)")


def iso_day(value):
    try:
        return date(*map(int, re.findall(r"\d+", value))).isoformat()
    except ValueError:
        return ""


def reference(row, claim):
    return {"材料": row["编号"], "来源": row["来源"], "发布时间": row["发布时间"],
            "引句": claim["原句"], "起点": claim["起点"], "终点": claim["终点"]}


def relation(kind, summary, *refs):
    return {"关系": kind, "说明": summary, "依据": list(refs)}


def verify(rows):
    reports = defaultdict(list)
    denials = defaultdict(list)
    originals = defaultdict(list)
    corrected = set()
    for row in rows:
        row["核验"] = []
        if row.get("事件类型") == "业绩":
            continue
        official = row["材料性质"] == "公告披露"
        published = row["发布时间"]
        correction = CORRECTION.fullmatch(row["正文"]) if official else None
        if correction:
            key = (row["来源"], iso_day(correction["date"]), correction["number"], correction["old"])
            matches = originals[key]
            if len(matches) == 1 and key not in corrected and matches[0][1]["发布时间"] < published:
                original, old_ref = matches[0]
                for field in ("公司", "对手", "项目", "合同编号", "事项编号"):
                    row[field] = original[field]
                row["待复核"] = []
                row["归并依据"] = "更正公告与原公告的发布者、原披露日、合同编号和原金额一致"
                claim = {"动作": "合同金额更正", "原句": row["正文"], "起点": 0, "终点": len(row["正文"])}
                row["说法"] = [claim]
                new = correction["new"]
                value, unit = re.fullmatch(r"([\d.]+)(亿元|万元|元)", new).groups()
                row["金额"] = [{"原文角色": "更正后合同金额", "数值": value, "单位": unit}]
                row["核验"].append(relation("金额更正", f"原披露 {correction['old']}，本次更正为 {new}",
                                           old_ref, reference(row, claim)))
                corrected.add(key)
            else:
                row["待复核"].append("更正未唯一对应可见且尚未更正的原金额")
            continue

        matter = row["事项编号"]
        if not matter:
            continue
        for claim in row["说法"]:
            action, quote = claim["动作"], claim["原句"]
            ref = reference(row, claim)
            if action == "称已签约" and not official and re.search(r"已与|已签约", quote):
                source = next((s for s in row["出处判断"] if s["本篇引句"] == ref), None)
                if source and len(source["报道链"]) <= 1:
                    reports[matter].append(ref)
            if official and action == "尚未签约" and re.search(r"截至(?:本公告披露时|目前|今日)", quote):
                for earlier in reports[matter]:
                    if earlier["发布时间"] < published:
                        row["核验"].append(relation("反证", "公司称截至披露时尚未签约，与此前报道的已签说法相反",
                                                   earlier, ref))
                denials[matter].append(ref)
            if official and action == "称已签约":
                signed = SIGN_DATE.search(quote)
                day = iso_day(signed[1]) if signed else ""
                earlier = [d for d in denials[matter] if d["发布时间"][:10] < day <= published[:10]]
                if earlier:
                    row["核验"].append(relation("后续签署", f"公司披露于 {day} 签署，签约日晚于此前澄清",
                                               earlier[-1], ref))
                number, _, issue = number_field(row)
                amounts = AMOUNT.findall(quote)
                if number and not issue and len(amounts) == 1:
                    key = (row["来源"], published[:10], number, "".join(amounts[0]))
                    originals[key].append((row, ref))
    return rows
