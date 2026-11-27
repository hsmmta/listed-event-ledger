"""按说法核对明确引用的材料、发布者、披露顺序及引用内容。"""
import re

from src.verify.contracts import reference

CITE = re.compile(r"^(?:转引|转载自|援引)([^（(，。]{1,40})[（(]稿号\s*([^）)\s]+)[）)](?:报道)?[，：:]\s*")
OUTLET_ONLY = re.compile(r"^(?:转引|转载自|援引)[^，。：]{1,45}报道[，：:]\s*")
MENTION = re.compile(r"转引|转载|援引|据.{1,40}报道")


def trace(rows):
    prior = {}
    for row in rows:
        row["出处判断"] = []
        for claim in row["说法"]:
            if row["材料性质"] == "公告披露":
                continue
            quote = claim["原句"]
            cite = CITE.match(quote)
            content = quote[cite.end():] if cite else OUTLET_ONLY.sub("", quote)
            ref = reference(row, claim)
            if cite:
                source, doc = cite.groups()
                parent = prior.get(doc)
                if row["引述来源"] == source + "（稿号" + doc + "）":
                    row["引述来源"] = source
                matches = []
                if (parent and parent["来源"] == source and parent["发布时间"] < row["发布时间"]
                        and parent["事项编号"] == row["事项编号"] and row["事项编号"]):
                    matches = [v for v in parent["出处判断"] if v["说法正文"] == content
                               and v["动作"] == claim["动作"] and v["报道链"]]
                chain = matches[0]["报道链"] + [ref] if len(matches) == 1 else []
                reason = "引述已有报道" if chain else "原稿缺失或引句无法唯一对应，来源独立性待核"
            elif MENTION.search(quote) or (row["材料性质"] == "转述" and
                                           not re.match(r"(?:本报|本台)记者(?:现场|独立)", quote)):
                chain, reason = [], "引述范围或原稿未能锁定，来源独立性待核"
            else:
                chain, reason = [ref], "本篇报道陈述"
            row["出处判断"].append({"动作": claim["动作"], "说法正文": content,
                                  "本篇引句": ref, "报道链": chain, "说明": reason})
        prior[row["编号"]] = row
    return rows
