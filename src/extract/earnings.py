"""窄口径解析明确报告期、归母净利润及金额的业绩披露。"""
from decimal import Decimal
import re

from src.link.resolve import SENTENCE


PERIOD = re.compile(r"(20\d{2})年(年度|度|半年度|第一季度|一季度|第三季度|前三季度)")
METRIC = r"(?:归母净利润|归属于上市公司股东的净利润)"
VALUE = r"([+-]?\d+(?:\.\d+)?)\s*"
UNIT = r"(亿元|万元|元)"
FIGURE = re.compile(METRIC + r"(?:预计)?(?:为|约为|为约)?\s*" + VALUE + UNIT
                    + r"?(?:\s*(?:至|到|~|～)\s*" + VALUE + UNIT + r")?(?=[。；，\n]|$)")
DISCLOSURE = re.compile(r"业绩预告|年度报告|季度报告|年报披露|实际披露")


def extract_earnings(source, body):
    if not (re.search(METRIC, body) and DISCLOSURE.search(body)):
        return None
    company = source[:-2] if source.endswith("公司公告") else ""
    periods = {year + "年" + {"一季度": "第一季度", "年度": "度"}.get(term, term)
               for year, term in PERIOD.findall(body)}
    period = next(iter(periods)) if len(periods) == 1 else ""
    result = {"事件类型": "业绩", "公司": company, "报告期": period, "指标": "归母净利润",
              "项目": period + "归母净利润", "对手": "", "材料性质": "公告披露" if company else "报道",
              "引述来源": "", "说法": [], "金额": [], "待复核": [], "业绩值": None}
    revision = re.search(r"业绩预告[（(]?修正|修正(?:后)?(?:的)?业绩预告", body)
    forecast = "预告" in body or "预计" in body
    actual = re.search(r"年度报告|季度报告|年报披露|实际披露", body)
    stage = "修正" if revision else ("预告" if forecast else "实际")
    matches = list(FIGURE.finditer(body))
    if (not company or not period or len(matches) != 1 or (forecast and actual)
            or re.search(r"同比|扣非|扣除非经常性损益|亏损|尚未|撤回|未确认|未披露|不实|有误|拟披露", body)):
        result["待复核"].append("发布主体、报告期、指标口径或数值适用范围待核")
        return result
    match = matches[0]
    low, unit1, high, unit2 = match.groups()
    unit = unit2 or unit1
    if (not unit or (unit1 and unit2 and unit1 != unit2) or
            (high and (stage == "实际" or Decimal(low) > Decimal(high)))):
        result["待复核"].append("金额单位、区间或披露阶段待核")
        return result
    sentence = next(s for s in SENTENCE.finditer(body) if s.start() <= match.start() < s.end())
    result["说法"] = [{"动作": stage, "原句": sentence.group(), "起点": sentence.start(), "终点": sentence.end()}]
    result["业绩值"] = {"阶段": stage, "下限": low, "上限": high or low, "单位": unit}
    return result
