"""Transparent screening and reading priority for a bounded candidate sample."""

import math
import re
from datetime import date

from .store import same_source
from .journal_metrics import journal_metric


HEAT_NAMES = {"low": "较少", "medium": "中等", "high": "较多", "unknown": "数据不足"}
MODES = {"auto": "按热度自动", "broad": "广泛收集", "strict": "优先高关注度"}
SCHOLARLY = {"article", "preprint", "report"}
STOP_WORDS = set("a an the for of in on to and or with by from at as using based study research".split())


def terms(text):
    text = re.sub(r"\bai\b", "artificial intelligence", text.casefold())
    text = re.sub(r"\bscientific\b", "science", text)
    result = set()
    for word in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", text):
        if word in STOP_WORDS:
            continue
        if re.search(r"[\u4e00-\u9fff]", word):
            result.update(word[i:i + 2] for i in range(max(1, len(word) - 1)))
        else:
            if len(word) > 4 and word.endswith("ies"):
                word = word[:-3] + "y"
            elif len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "ics")):
                word = word[:-1]
            result.add(word)
    return result


def relevance(record, query):
    semantic = record.get("semantic_relevance", {})
    if semantic.get("queries") == query and semantic.get("score") in (0, .65, .85, 1):
        return semantic["score"]
    if isinstance(query, list):
        return max((relevance(record, q) for q in query), default=0.0)
    wanted = terms(query)
    if not wanted:
        return 0.0
    title = terms(record.get("title", ""))
    content = title | terms(record.get("text", ""))
    # Authors and venue names must not make an otherwise unrelated item relevant.
    coverage = len(wanted & content) / len(wanted)
    title_coverage = len(wanted & title) / len(wanted)
    if coverage < 0.75 or title_coverage < 0.5:
        return 0.0
    return round(0.65 * title_coverage + 0.35 * coverage, 3)


def year_of(record):
    value = str(record.get("year", ""))
    return int(value) if re.fullmatch(r"\d{4}", value) else None


def exclusion(record, query, year):
    if record.get("record_type") in {"peer-review", "component", "journal", "journal-issue", "journal-volume", "dataset"}:
        return "评审记录、期刊目录或数据附件，不作为研究文献入选"
    if record.get("is_retracted") or re.match(
            r"^\s*(?:\(withdrawn\)|withdrawn\b|retracted\b|retraction\s*[:：]|retraction (?:of|note)\b|correction (?:to|of)\b|correction\s*[:：]|erratum\b)",
            record.get("title", ""), re.I):
        return "撤回、撤稿或更正通知，需人工核验"
    if year_of(record) and year_of(record) > year:
        return "标注年份晚于当前年份，暂不自动收录"
    semantic = record.get("semantic_relevance", {})
    if semantic.get("queries") == query and semantic.get("score", 0) < .85:
        return "语义核查：仅外围背景或无关，暂不纳入主题主目录；" + semantic.get("reason", "")
    if relevance(record, query) < 0.65:
        return "题名/摘要与检索词匹配不足（未使用作者或期刊名匹配）"
    return ""


def unique(records):
    result = []
    for record in records:
        if not any(same_source(old, record) for old in result):
            result.append(record)
    return result


def same_title_year(a, b):
    # Limit redundant slots without merging possibly distinct DOI/book editions.
    norm = lambda text: re.sub(r"[\W_]", "", text.casefold())
    return bool(a.get("year") and a["year"] == b.get("year") and a.get("kind") == b.get("kind")
                and norm(a["title"]) == norm(b["title"]))


def assess_heat(recent_records, query, measured, year=None):
    year = year or date.today().year
    eligible = unique([r for r in recent_records if r.get("kind") in SCHOLARLY
                       and not exclusion(r, query, year) and year - 2 <= (year_of(r) or 0) <= year])
    count = len(eligible)
    level = "unknown" if not measured or not count else "high" if count >= 40 else "medium" if count >= 15 else "low"
    return {"level": level, "label": HEAT_NAMES[level], "recent_count": count,
            "window": f"{year - 2}–{year}", "providers": measured,
            "basis": "各论文来源近三个日历年最多100条候选（多检索式均分配额），去重并检查题名/摘要；≥40条较多、15–39条中等、1–14条较少。"
                     "这是候选集活跃度代理，不是全领域发文量或学术质量评价。"}


def attention_rate(record, year):
    count = record.get("citation_metrics", {}).get("count")
    published = year_of(record)
    if count is None or not published or published > year:
        return None
    return count / max(1, year - published + 1)


def rank_sources(records, query, year=None):
    """Reading aid, not a judgement of scientific quality; unknown metrics are omitted."""
    year = year or date.today().year
    pools = {}
    for record in records:
        metric = record.get("citation_metrics", {})
        rate = attention_rate(record, year)
        if not record.get("excluded") and relevance(record, query) and rate is not None:
            pools.setdefault(metric.get("provider", "unknown"), []).append((metric["count"], rate))

    def percentile(value, values):
        return (sum(v < value for v in values) + .5 * sum(v == value for v in values)) / len(values)

    ranked = []
    for record in records:
        metric = journal_metric(record)
        components = [("相关性", 60, relevance(record, query)),
                      ("原文覆盖", 5, {"metadata": 0, "abstract": .6, "excerpt": .8, "fulltext": 1}.get(record.get("evidence_level"), 0))]
        rate = attention_rate(record, year)
        pool = pools.get(record.get("citation_metrics", {}).get("provider", "unknown"), [])
        if rate is not None and pool and not record.get("excluded"):
            count = record["citation_metrics"]["count"]
            attention = (percentile(count, [p[0] for p in pool]) + percentile(rate, [p[1] for p in pool])) / 2
            components.append(("论文关注度", 20, attention))
        if metric.get("value") is not None:
            components.append(("期刊IF", 10, min(1, math.log1p(metric["value"]) / math.log1p(50))))
        published = year_of(record)
        if published and published <= year:
            components.append(("时效", 5, max(0, 1 - (year - published) / 10)))
        score = round(100 * sum(weight * value for _, weight, value in components) / sum(w for _, w, _ in components), 1)
        reasons = "；".join(f"{name} {value:.2f} × {weight}" for name, weight, value in components)
        if record.get("semantic_relevance", {}).get("queries") == query:
            reasons += "；AI 相关性判断：" + record["semantic_relevance"]["reason"]
        importance = {"score": score, "rank": None, "reason": reasons,
                      "rule": "相关性60/论文关注度20/期刊IF10/原文覆盖5/时效5；缺失或不适用项不计并重分权重。关注度为本主题同来源的累计引用与年均引用百分位均值；分数只作阅读优先级。"}
        ranked.append({**record, "journal_metrics": metric, "importance": importance})
    ranked.sort(key=lambda r: (bool(r.get("excluded")), -r["importance"]["score"], r.get("id", r["title"])))
    position = 0
    for record in ranked:
        if not record.get("excluded"):
            position += 1
            record["importance"]["rank"] = position
    return ranked


def screen(records, query, heat, limit, mode="auto", year=None):
    if mode not in MODES:
        raise ValueError("筛选模式无效")
    year = year or date.today().year
    level = "high" if mode == "strict" else "low" if mode == "broad" else heat["level"]
    records = rank_sources(unique(records), query, year)
    eligible = [r for r in records if not exclusion(r, query, year)]
    papers = [r for r in eligible if r.get("kind") in SCHOLARLY]
    rates = sorted(rate for r in papers if (rate := attention_rate(r, year)) is not None)
    quantile = 0.75 if level == "high" else 0.5
    threshold = max(2.0 if level == "high" else 1.0,
                    rates[math.ceil(len(rates) * quantile) - 1] if rates else 0)
    focused = level in ("high", "medium") and bool(papers)
    selected, paths = [], {}

    def take(items, count, path):
        added = 0
        for record in items:
            if record in selected or any(same_title_year(record, old) for old in selected):
                continue
            if len(selected) >= limit or added >= count:
                break
            selected.append(record)
            paths[id(record)] = path
            added += 1

    by_relevance = lambda r: (relevance(r, query), bool(r.get("text")), attention_rate(r, year) or 0, year_of(r) or 0)
    if focused and papers:
        core = sorted([r for r in papers if (attention_rate(r, year) or 0) >= threshold or
                       (r["journal_metrics"].get("value") or 0) >= (10 if level == "high" else 5)],
                      key=lambda r: r["importance"]["score"], reverse=True)
        # Low-citation new work has its own quota; it is not labelled high-impact.
        frontier = sorted([r for r in papers if year - 1 <= (year_of(r) or 0) <= year],
                          key=lambda r: (attention_rate(r, year) or 0, by_relevance(r)), reverse=True)
        basic = sorted([r for r in eligible if r not in papers], key=by_relevance, reverse=True)
        basic_slots = min(len(basic), math.floor(limit * 0.2))
        frontier_slots = math.floor(limit * 0.3)
        classic = sorted([r for r in papers if (year_of(r) or year) < year - 5
                          and (r.get("citation_metrics", {}).get("count") or 0) >= 50],
                         key=lambda r: (r["citation_metrics"]["count"], relevance(r, query)), reverse=True)
        classic_slots = min(len(classic), math.floor(limit * .1))
        take(core, limit - frontier_slots - basic_slots - classic_slots, "高关注度")
        take(frontier, frontier_slots, "近期研究")
        take(classic, classic_slots, "经典文献")
        take(basic, basic_slots, "基础/机构资料")
        take(core, limit, "高关注度")
    else:
        take(sorted(eligible, key=lambda r: r["importance"]["score"], reverse=True), limit, "相关性收录")

    audit = []
    for record in records:
        selected_path = paths.get(id(record))
        reason = exclusion(record, query, year)
        if selected_path == "高关注度":
            rate = attention_rate(record, year)
            reason = (f"年均引用估值 {rate:.2f} ≥ 本来源门槛 {threshold:.2f}" if rate is not None and rate >= threshold
                      else f"已核实期刊 IF {record['journal_metrics']['value']}（{record['journal_metrics']['year']}）达到本次 IF 通道门槛")
        elif selected_path == "经典文献":
            reason = "较早发表且本来源累计引用≥50的相关文献，保留经典通道；年代或引用量不自动证明其奠基性"
        elif selected_path == "近期研究":
            reason = f"{year - 1}–{year} 年相关研究，保留近期名额；低引用或缺失引用不代表低质量"
        elif selected_path:
            reason = "按题名/摘要相关性纳入；书籍及机构资料不套用论文引用门槛" if record not in papers else "当前策略按相关性收录"
        elif not reason and any(same_title_year(record, old) for old in selected):
            reason = "暂缓：同题名、同年份的可能版本已有入选，不重复占用名额；保留独立 DOI/版本记录供核验"
        elif not reason:
            reason = "暂缓：未达到本次关注度门槛或超出相应名额；可改用广泛收集或手工导入"
        audit.append({"record": record, "selected": bool(selected_path), "path": selected_path or "未入选",
                      "reason": reason, "relevance": relevance(record, query),
                      "annual_citations": attention_rate(record, year)})
    policy = {"level": level, "mode": mode, "mode_label": MODES[mode],
              "annual_citation_threshold": round(threshold, 6) if focused else None,
              "percentile": int(quantile * 100) if focused else None,
              "metric_count": len(rates), "relevant_count": len(eligible), "selected": len(selected),
              "rule": ("论文可经引用或已核实IF通道进入核心候选，按重要度排序；预留30%近期、最多10%经典及20%基础资料；不足名额不强行填满。"
                       if focused and papers else "按题名/摘要相关性收录，书籍和可信网站不使用论文引用门槛。")}
    return audit, policy
