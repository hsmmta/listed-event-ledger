import re

SIGNING_TOPIC = re.compile(r"(?:签署|签订)(?:情况|事宜|进展)")

def extract(source, body):
    # 每个范围都来自原始字符串，方便定位；规则只覆盖合同语料。
    company = re.match(r"(.+公司)公告$", source)
    company = company or re.search(r"(?:^|[，。；])([\u4e00-\u9fffA-Za-z0-9]{1,18}?公司)(?=已|拟|为|与|于|尚)", body)
    company = company.group(1) if company else ""
    linked = re.search(r"(?:转引|转载自|援引)([^，。；：:]{1,40}?)(?:今晨报道|此前报道|报道|[，：:])", body)
    mode = "转述" if linked else ("公告披露" if source.endswith("公司公告") else "报道")
    parties = re.findall(r"与([^，。；、]{2,24}?)(?=(?:已|正式)?(?:签订|签署))", body)
    if not parties:
        # 紧邻项目名且没有分隔的对手，仅拆解能辨认的匿名组织名。
        parties = re.findall(r"为((?:园区|集团|企业|公司)[甲乙丙丁戊己庚辛壬癸])(?=[^，。；]{2,30}项目)", body)
    # 项目名称从签署动作或候选资格前取出；上下文不足时留空。
    names = re.findall(r"(?:签订|签署)(?:了)?(?:《)?([^，。；》]{2,35}?)(?:项目)?合同", body)
    names = [n for n in names if n not in {"正式", "相关", "上述", "该项"} and "正式" not in n]
    if not names and parties:
        m = re.search(re.escape(parties[0])+r"([^，。；]{2,30}?)项目(?:第一|的第一|中标)", body)
        if m:
            names = [m.group(1)]
    projects = list(dict.fromkeys(names))
    project = projects[0] if len(projects) == 1 else ""
    claims = []
    for sent in re.finditer(r"[^。！？；\n]+[。！？；]?", body):
        quote = sent.group()
        actions = []
        # 标题中的“签署情况”等词组不陈述动作；引句仍使用未经改写的正文。
        action_text = SIGNING_TOPIC.sub("，", quote)
        if "候选人" in quote:
            actions.append("候选")
        if re.search(r"(?:尚未|未曾|并未|没有|未)(?:正式)?(?:签订|签署|签约)", action_text):
            actions.append("尚未签约")
        elif re.search(r"(?:拟|预计|计划|有望|拟于|将)[^，。；]{0,24}(?:签订|签署|签约)", action_text):
            actions.append("拟签约")
        elif re.search(r"签订|签署|已签约", action_text):
            actions.append("称已签约")
        if re.search(r"否认|不实|误传|撤回|撤稿|更正", quote):
            actions = ["否认或更正（待核范围）"]
        for action in actions:
            claims.append({"动作":action, "原句":quote, "起点":sent.start(), "终点":sent.end()})
    amounts = re.findall(r"(合同金额|项目总投资|金额)(?:约为|为|约|达)?\s*([0-9.,]+)\s*(亿元|万元|元)", body)
    reasons = []
    if not company or not project or not parties or len(set(parties)) != 1:
        reasons.append("主体、对手或项目待核")
    if not claims:
        reasons.append("缺少已覆盖的合同动作")
    if re.search(r"否认|不实|误传|撤回|撤稿|更正", body):
        reasons.append("否认或更正的作用范围待核")
    return {"公司":company,"对手":parties[0] if len(set(parties))==1 else "",
            "项目":project,"材料性质":mode,"引述来源":linked.group(1) if linked else "",
            "说法":claims, "金额":[{"原文角色":k,"数值":v,"单位":u} for k,v,u in amounts],
            "待复核":reasons}
