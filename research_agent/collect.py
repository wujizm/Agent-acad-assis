import html
import json
import re
import uuid
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .screening import MODES, assess_heat, screen, unique, rank_sources
from .store import atomic_text, canonical_doi, now


def strip_markup(text):
    return html.unescape(re.sub(r"<[^>]*>", " ", text or "")).strip()


def provenance(provider, url):
    return [{"provider": provider, "url": url, "retrieved_at": now()}]


def brief(text):
    if not text:
        return "未获取摘要或正文，暂不能概述研究内容。"
    return "原文摘录（未概括）：" + re.split(r"(?<=[。！？])|(?<=[.!?])\s", text.strip())[0][:240]


def crossref_record(item):
    authors, affiliations = [], []
    for author in item.get("author", []):
        name = author.get("name") or " ".join(filter(None, [author.get("given"), author.get("family")]))
        authors.append(name)
        units = [a["name"] for a in author.get("affiliation", []) if a.get("name")]
        if units:
            affiliations.append(name + "：" + "；".join(units))
    date = item.get("published", item.get("published-print", item.get("issued", {}))).get("date-parts", [[]])
    text = strip_markup(item.get("abstract", ""))
    kind = {"journal-article": "article", "proceedings-article": "article", "book": "book", "edited-book": "book", "monograph": "book", "book-chapter": "chapter",
            "report": "report", "standard": "standard", "posted-content": "preprint"}.get(item.get("type"), "other")
    doi = canonical_doi(item.get("DOI", ""))
    return {"title": strip_markup(" ".join(item.get("title", []))), "kind": kind, "record_type": item.get("type", ""),
            "venue": strip_markup("; ".join(item.get("container-title", [])) or item.get("publisher", "")),
            "issn": item.get("ISSN", []),
            "authors": "; ".join(filter(None, authors)), "affiliations": "\n".join(affiliations),
            "year": str(date[0][0]) if date and date[0] else "", "doi": doi,
            "isbn": next(iter(item.get("ISBN", [])), ""), "url": "https://doi.org/" + doi if doi else item.get("URL", ""),
            "text": text, "summary": brief(text), "evidence_level": "abstract" if text else "metadata",
            "notes": "Crossref 注册元数据；收录不代表内容已核实。",
            "citation_metrics": {"count": item.get("is-referenced-by-count"), "provider": "Crossref", "retrieved_at": now()},
            "raw_metadata": item, "provenance": provenance("Crossref", "https://api.crossref.org/works/" + doi)}


def book_record(item):
    return {"title": item.get("title", ""), "kind": "book", "venue": "; ".join(item.get("publisher", [])[:3]),
            "authors": "; ".join(item.get("author_name", [])), "year": str(item.get("first_publish_year", "")),
            "url": "https://openlibrary.org" + item["key"], "evidence_level": "metadata", "summary": brief(""),
            "notes": "Open Library 作品级目录；年份为首版年份，出版社可能涉及多个版本。未读取整本书；请补充具体版本及章节。",
            "raw_metadata": item, "provenance": provenance("Open Library", "https://openlibrary.org" + item["key"])}


def openalex_record(item):
    words = {}
    for word, positions in (item.get("abstract_inverted_index") or {}).items():
        for position in positions:
            words[position] = word
    text = " ".join(words[k] for k in sorted(words))
    authors, units = [], []
    for a in item.get("authorships", []):
        name = a.get("author", {}).get("display_name", "")
        authors.append(name)
        institutions = [i.get("display_name", "") for i in a.get("institutions", [])]
        if institutions:
            units.append(name + "：" + "；".join(institutions))
    location = item.get("primary_location") or {}
    return {"title": item.get("title") or item.get("display_name", ""),
            "kind": {"article": "article", "book": "book", "book-chapter": "chapter", "preprint": "preprint", "report": "report"}.get(item.get("type"), "other"),
            "record_type": item.get("type", ""), "is_retracted": bool(item.get("is_retracted")),
            "citation_metrics": {"count": item.get("cited_by_count"), "provider": "OpenAlex", "retrieved_at": now()},
            "venue": (location.get("source") or {}).get("display_name", ""),
            "issn": (location.get("source") or {}).get("issn") or [],
            "authors": "; ".join(authors), "affiliations": "\n".join(units), "year": str(item.get("publication_year") or ""),
            "doi": canonical_doi(item.get("doi") or ""), "url": item.get("doi") or location.get("landing_page_url") or item["id"],
            "text": text, "summary": brief(text), "evidence_level": "abstract" if text else "metadata",
            "notes": "OpenAlex 聚合元数据；作者单位关联需对照原文核验。", "raw_metadata": item,
            "provenance": provenance("OpenAlex", item["id"])}


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self.meta = [], [], {}
        self.hidden, self.in_title = 0, False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "noscript"):
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        attrs = dict(attrs)
        if tag == "meta":
            key = (attrs.get("name") or attrs.get("property") or "").lower()
            self.meta.setdefault(key, []).append(attrs.get("content", ""))
        if tag in ("p", "div", "br", "h1", "h2", "h3", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "noscript"):
            self.hidden = max(0, self.hidden - 1)
        if tag == "title":
            self.in_title = False
        if tag in ("p", "div", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        elif not self.hidden:
            self.parts.append(data)

    def text(self):
        return "\n".join(line.strip() for line in "".join(self.parts).splitlines() if line.strip())


def extract_file(data, filename):
    if filename.lower().endswith(".pdf") or data.startswith(b"%PDF"):
        import pymupdf
        try:
            with pymupdf.open(stream=data, filetype="pdf") as doc:
                if doc.needs_pass:
                    raise ValueError("PDF 已加密，请先提供可读取版本")
                text = "\n\n".join(f"[第 {i + 1} 页]\n{page.get_text()}" for i, page in enumerate(doc))
                metadata = dict(doc.metadata or {})
                if len(re.sub(r"\[第 \d+ 页\]|\s", "", text)) < 40:
                    raise ValueError("PDF 未提取到足够文字，可能是扫描件；请先 OCR，或导入可复制的文字")
                return text, metadata
        except pymupdf.FileDataError as exc:
            raise ValueError("无法读取该 PDF") from exc
    if not filename.lower().endswith((".txt", ".md")):
        raise ValueError("支持 PDF、UTF-8 TXT 和 Markdown 文件")
    try:
        return data.decode("utf-8-sig"), {}
    except UnicodeDecodeError as exc:
        raise ValueError("文本文件请保存为 UTF-8 编码") from exc


def fetch_url(network, url):
    payload, content_type, final_url = network.get(url)
    if "application/pdf" in content_type or payload.startswith(b"%PDF"):
        text, meta = extract_file(payload, "document.pdf")
        return {"title": meta.get("title") or urlsplit(final_url).path.rsplit("/", 1)[-1] or "PDF 文献",
                "authors": meta.get("author", ""), "url": final_url, "text": text,
                "summary": brief(text), "kind": "other", "evidence_level": "fulltext",
                "notes": "从网址提取 PDF 文本；题名、作者及版式提取结果待核验。",
                "provenance": provenance("网页 PDF", final_url)}, payload, ".pdf"
    if "html" not in content_type and content_type and "text/plain" not in content_type:
        raise ValueError("该网址未返回 HTML、文本或 PDF")
    charset = re.search(r"charset=([\w-]+)", content_type, re.I)
    page = PageText()
    try:
        page.feed(payload.decode(charset.group(1) if charset else "utf-8", errors="replace"))
    except LookupError:
        page.feed(payload.decode("utf-8", errors="replace"))
    first = lambda key: next(iter(page.meta.get(key, [])), "")
    title = first("citation_title") or first("og:title") or "".join(page.title).strip() or final_url
    text = page.text()
    if len(text) < 80:
        raise ValueError("网页未提取到足够正文，可能需要登录或 JavaScript；可手工粘贴正文")
    date = first("citation_publication_date") or first("article:published_time")
    return {"title": title, "venue": first("citation_journal_title") or urlsplit(final_url).hostname,
            "authors": "; ".join(page.meta.get("citation_author", []) or page.meta.get("author", [])),
            "affiliations": "", "year": date[:4] if re.match(r"\d{4}", date) else "",
            "doi": first("citation_doi"), "url": final_url, "text": text, "summary": brief(text),
            "evidence_level": "excerpt", "kind": "web", "raw_metadata": page.meta,
            "notes": "自动提取的网页正文，可能含导航/缺漏；不等同于论文或书籍全文。",
            "provenance": provenance("网页", final_url)}, payload, ".html"


def trusted_domains(value):
    result = []
    for part in re.split(r"[,，;；\s]+", value.strip()):
        if not part:
            continue
        domain = urlsplit(part if "://" in part else "https://" + part).hostname
        if not domain or "." not in domain or not re.fullmatch(r"[a-zA-Z0-9.-]+", domain):
            raise ValueError("可信域名格式无效，例如 nist.gov")
        result.append(domain.lower())
    return result


class Collector:
    def __init__(self, config, network, store, llm=None):
        self.config, self.net, self.store = config, network, store
        self.llm = llm

    def queries(self, topic, progress):
        original = [q.strip() for q in re.split(r"[;；\n]", topic["query"]) if q.strip()][:5]
        if len(original) > 1 or not self.llm or not self.llm.ready:
            return original, original, []
        progress("正在生成英文检索式：主题术语、同义词与经典方法")
        try:
            result = self.llm.complete("为学术资料库设计检索式。只输出 JSON 对象，queries 为 4–5 个英文论文检索式，book_queries 为 1–2 个英文书籍检索式。"
                "每个论文检索式2–5个词，一条只表达一个概念，不把多个理论或方法塞进同一条。前两条使用主题的通行名称和同义词，后几条覆盖核心理论及代表方法。"
                "不要例行添加 review、research 等限制词，以免漏掉重要论文。书籍检索式2–4词，可使用其所属学科的教材名称或领域术语，不用长论文检索式找书。"
                "中文主题需译为该领域通行术语，不要逐字硬译。避免单独使用 machine learning、AI、materials 等宽泛词。"
                "不要生成论文标题、作者、DOI 或研究结论。输出的是检索词，不是资料证据。\n"
                + json.dumps({"topic": topic["name"], "query": topic["query"]}, ensure_ascii=False), json_output=True)
            queries = result.get("queries")
            if not isinstance(queries, list) or not 1 <= len(queries) <= 5 or any(
                    not isinstance(q, str) or not 4 <= len(q.strip()) <= 120 or "\n" in q for q in queries):
                raise ValueError("检索式格式不符合要求")
            books = result.get("book_queries", queries[:2])
            if not isinstance(books, list) or not 1 <= len(books) <= 2 or any(
                    not isinstance(q, str) or not 4 <= len(q.strip()) <= 120 for q in books):
                books = queries[:2]
            return list(dict.fromkeys(q.strip() for q in queries)), books, []
        except ValueError as exc:
            return original, original, [f"检索式扩展失败，使用原检索词：{exc}"]

    def assess_relevance(self, topic, records, queries, progress):
        """Use title/abstract semantics to avoid literal keyword false positives."""
        if not self.llm or not self.llm.ready or not records:
            return records, []
        records, warnings = unique(records), []
        for start in range(0, len(records), 60):
            batch = records[start:start + 60]
            progress(f"正在核查主题相关性：{start + 1}–{start + len(batch)} / {len(records)}")
            evidence = [{"index": i, "title": r["title"], "year": r.get("year"), "kind": r.get("kind"),
                         "abstract": r.get("text", "")[:500]} for i, r in enumerate(batch)]
            try:
                result = self.llm.complete("判断候选资料与用户主题的语义相关性，只依据提供的题名/摘要，不补造论文内容或质量结论。"
                    "宽主题优先概述和核心方法；具体应用可相关但不等同整体方向。若主题是理论/原理，仅工艺或器件性能改进、未解释或检验机制的应用只给0.65。注意同词异义、历史上已被替代的理论与当前理论的区别。"
                    "返回 JSON {items:[{index,score,reason}]}，每个 index 恰好一次。score 只取 1（直接综述/核心理论方法）、"
                    "0.85（直接相关应用/专题）、0.65（外围或仅历史背景）、0（无关）。reason 是不超过40字的中文判断依据。"
                    "书籍可作为基础知识资料，不因没有摘要就排除；不确定的论文保守评分，不把输出当作内容证据。\n"
                    + json.dumps({"topic": topic["name"], "scope": topic["query"], "candidates": evidence}, ensure_ascii=False), json_output=True)
                items = result.get("items", [])
                if (not isinstance(items, list) or not all(isinstance(item, dict) for item in items)
                        or len(items) != len(batch) or {item.get("index") for item in items} != set(range(len(batch)))
                        or any(item.get("score") not in (0, .65, .85, 1) or not isinstance(item.get("reason"), str) for item in items)):
                    raise ValueError("相关性判断格式不完整")
                for item in items:
                    batch[item["index"]]["semantic_relevance"] = {"queries": queries, "score": item["score"],
                        "reason": item["reason"][:160], "assessed_at": now(), "basis": "AI 题名/摘要判断，非内容核验"}
            except (ValueError, TypeError, KeyError) as exc:
                warnings.append(f"语义相关性核查失败，使用词项匹配：{exc}")
        return records, warnings

    def rerank(self, topic_id, queries=None):
        topic = self.store.topic(topic_id)
        queries = queries or (self.store.last_search(topic_id) or {}).get("queries") or topic["query"]
        records = rank_sources(self.store.sources(topic_id), queries)
        for record in records:
            self.store.save_source(topic_id, record, record["id"])
        return {"updated": len(records), "note": "已按最新资料与已核实 IF 重新计算重要度；原有报告需重新生成。"}

    def run(self, topic_id, per_provider, progress, mode="auto"):
        if mode not in MODES:
            raise ValueError("筛选模式无效")
        topic = self.store.topic(topic_id)
        query = topic["query"]
        per_provider = max(1, min(25, int(per_provider)))
        queries, book_queries, warnings = self.queries(topic, progress)
        counts, candidates, recent, measured = {}, {}, [], []
        paper_providers = ["Crossref"] + (["OpenAlex"] if self.config.openalex_api_key else [])
        today = date.today()
        for name in paper_providers:
            candidates[name] = []
            successes, errors = 0, []
            searches = [(q, is_recent, 100 // len(queries) + (i < 100 % len(queries)))
                        for is_recent in (False, True) for i, q in enumerate(queries)]
            for search_query, is_recent, rows in searches:
                progress(f"正在搜集：{name} · {'近期热度采样' if is_recent else '候选资料'} · {search_query}")
                start = f"{today.year - 2}-01-01"
                try:
                    if name == "Crossref":
                        params = {"query.title": search_query, "rows": rows,
                                  "filter": (f"from-pub-date:{start}," if is_recent else "") + f"until-pub-date:{today.isoformat()}"}
                        data = self.net.json("https://api.crossref.org/works", params)["message"]
                        records = [crossref_record(i) for i in data["items"] if i.get("title")]
                    else:
                        params = {"search": search_query, "per-page": rows, "api_key": self.config.openalex_api_key,
                                  "filter": (f"from_publication_date:{start}," if is_recent else "") + f"to_publication_date:{today.isoformat()}"}
                        data = self.net.json("https://api.openalex.org/works", params)
                        records = [openalex_record(i) for i in data["results"] if i.get("title") or i.get("display_name")]
                    candidates[name].extend(records)
                    successes += 1
                    if is_recent:
                        recent.extend(records)
                        if name not in measured:
                            measured.append(name)
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append(str(exc))
                    warnings.append(f"{name} · {search_query} · {'近期采样' if is_recent else '候选检索'}失败：{exc}")
            if not successes:
                counts[name] = {"error": "；".join(errors), "added": 0, "merged": 0}
                candidates.pop(name)
        providers = [
            ("Open Library", lambda: [book_record(i) for q in book_queries for i in self.net.json("https://openlibrary.org/search.json",
                {"q": q, "limit": max(1, 50 // len(book_queries)), "fields": "key,title,author_name,first_publish_year,publisher"}).get("docs", [])])]
        if not self.config.openalex_api_key:
            warnings.append("OpenAlex 未配置，未执行该来源；部分摘要和作者单位可能缺失。")
        domains = trusted_domains(topic["domains"])
        if self.config.brave_search_api_key and domains:
            providers.append(("可信网站", lambda: [r for q in queries for r in self.web_records(q, domains, max(1, 20 // len(queries)))]))
        else:
            warnings.append("可信网站自动搜索需要 BRAVE_SEARCH_API_KEY 和主题域名列表；仍可导入指定网址。")
        for name, search in providers:
            progress("正在搜集：" + name)
            try:
                candidates[name] = [r for r in search() if r.get("title")]
            except (ValueError, KeyError, TypeError) as exc:
                warnings.append(f"{name} 失败：{exc}")
                counts[name] = {"error": str(exc), "added": 0, "merged": 0}
        all_records, semantic_warnings = self.assess_relevance(topic, [r for group in candidates.values() for r in group], queries, progress)
        warnings.extend(semantic_warnings)
        # Copy assessments to all versions, including the separate recent sample.
        from .store import same_source
        for record in recent + [r for group in candidates.values() for r in group]:
            match = next((r for r in all_records if same_source(r, record)), None)
            if match and match.get("semantic_relevance"):
                record["semantic_relevance"] = match["semantic_relevance"]
        heat = assess_heat(recent, queries, measured, today.year)
        policies, audit = {}, []
        timestamp = now()
        for name, records in candidates.items():
            progress("正在筛选并归档：" + name)
            decisions, policy = screen(records, queries, heat, per_provider, mode, today.year)
            policies[name] = policy
            added = updated = 0
            for decision in decisions:
                entry = {**decision, "provider": name}
                if decision["selected"]:
                    record = {**decision["record"], "screening": {"mode": MODES[mode], "heat": heat["label"],
                              "path": decision["path"], "reason": decision["reason"], "assessed_at": timestamp}}
                    source, created = self.store.save_source(topic_id, record)
                    entry["source_id"] = source["id"]
                    added += int(created)
                    updated += int(not created)
                audit.append(entry)
            counts[name] = {"added": added, "merged": updated, "returned": len(unique(records)),
                            "selected": policy["selected"], "deferred": len(decisions) - policy["selected"]}
        if candidates and not any(c.get("selected", 0) for c in counts.values()):
            warnings.append("本次没有候选达到筛选条件；请检查检索词，或选择广泛收集。已有资料保留。")
        result = {"query": query, "queries": queries, "book_queries": book_queries, "crossref_search_field": "title", "time": timestamp, "mode": mode, "counts": counts, "heat": heat,
                  "policies": policies, "warnings": warnings,
                  "note": "仅对有限候选集筛选，非穷尽检索。IF 使用公开核实的指定年份期刊数据，缺失不记为0；引用数与IF分别记录。重要度是本主题阅读优先级，非论文质量评价。"}
        folder = self.store.topic_dir(topic_id)
        # Keep every run's decisions so rejected candidates remain inspectable after a retry.
        audit_name = "searches/" + timestamp.replace(":", "-") + "-" + uuid.uuid4().hex[:8] + ".json"
        result["audit_file"] = audit_name
        atomic_text(folder / audit_name, json.dumps({**result, "decisions": audit}, ensure_ascii=False, indent=2))
        atomic_text(folder / "last_search.json", json.dumps(result, ensure_ascii=False, indent=2))
        if counts and all("error" in value for value in counts.values()):
            raise ValueError("所有搜集来源均连接失败；已有资料未改变。" + "；".join(
                f"{name}：{value['error']}" for name, value in counts.items()))
        self.rerank(topic_id, queries)
        return result

    def web_records(self, query, domains, count):
        data = self.net.json("https://api.search.brave.com/res/v1/web/search",
            {"q": query + " (" + " OR ".join("site:" + d for d in domains) + ")", "count": min(count, 20)},
            {"X-Subscription-Token": self.config.brave_search_api_key})
        result = []
        for item in data.get("web", {}).get("results", []):
            host = urlsplit(item["url"]).hostname or ""
            if not any(host == d or host.endswith("." + d) for d in domains):
                continue
            text = strip_markup(item.get("description", ""))
            result.append({"title": item["title"], "url": item["url"], "venue": host, "kind": "web",
                           "text": text, "summary": brief(text), "evidence_level": "excerpt" if text else "metadata",
                           "notes": "搜索引擎片段，未获取网页全文。域名匹配采集范围，内容待核验；可用“抓取原文”补充。",
                           "raw_metadata": item, "provenance": provenance("Brave Search", item["url"])})
        return result
