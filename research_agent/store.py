import hashlib
import json
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


LEVELS = {"metadata": "仅书目信息", "abstract": "摘要", "excerpt": "节选/网页正文", "fulltext": "上传的全文文本"}
FIELDS = ("title", "title_zh", "title_en", "kind", "venue", "authors", "affiliations", "year",
          "doi", "isbn", "url", "summary", "main_content", "text", "evidence_level", "notes", "verified", "excluded")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_doi(value):
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", str(value).strip(), flags=re.I).lower().rstrip(".")


def canonical_url(value):
    parts = urlsplit(str(value).strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), ""))


def same_source(a, b):
    if a.get("file_sha256") and a.get("file_sha256") == b.get("file_sha256"):
        return True
    for key in ("doi", "isbn"):
        if a.get(key) and b.get(key):
            return a[key] == b[key]
    if a.get("url") and b.get("url") and canonical_url(a["url"]) == canonical_url(b["url"]):
        return True
    if a.get("kind") == "book" or b.get("kind") == "book":
        return False  # Editions cannot safely be merged by title alone.
    norm = lambda s: re.sub(r"[\W_]", "", s.casefold())
    return bool(a.get("year") and b.get("year") and a["year"] == b["year"]
                and norm(a["title"]) == norm(b["title"]))


def chunks(text, size=1400, overlap=160):
    text = text.strip()
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + size // 2, end)
            if boundary > start:
                end = boundary
        yield text[start:end]
        if end == len(text):
            break
        start = end - overlap


def digest(source):
    return hashlib.sha256(json.dumps({k: source.get(k) for k in
        ("title", "text", "evidence_level", "venue", "authors", "affiliations", "year")},
        sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def atomic_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "library.sqlite3"
        self.lock = threading.RLock()
        with self.connect() as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, query TEXT NOT NULL,
                    domains TEXT NOT NULL, created_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, topic_id INTEGER NOT NULL REFERENCES topics(id), data TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS source_topic ON sources(topic_id);
                CREATE TABLE IF NOT EXISTS chunks (
                    source_id TEXT NOT NULL REFERENCES sources(id), topic_id INTEGER NOT NULL,
                    ordinal INTEGER NOT NULL, text TEXT NOT NULL,
                    PRIMARY KEY(source_id, ordinal));
                CREATE INDEX IF NOT EXISTS chunk_topic ON chunks(topic_id);
                CREATE TABLE IF NOT EXISTS reports (
                    topic_id INTEGER NOT NULL, kind TEXT NOT NULL, revision INTEGER NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(topic_id, kind));
            """)

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            with con:
                yield con
        finally:
            con.close()

    def topic(self, topic_id):
        with self.connect() as con:
            row = con.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
        if not row:
            raise ValueError("主题不存在")
        return dict(row)

    def topics(self):
        with self.connect() as con:
            return [dict(r) for r in con.execute("""SELECT t.*, COUNT(s.id) AS source_count
                FROM topics t LEFT JOIN sources s ON t.id=s.topic_id GROUP BY t.id ORDER BY t.id DESC""")]

    def create_topic(self, name, query="", domains=""):
        name = str(name).strip()
        if not name or len(name) > 160:
            raise ValueError("请输入 1–160 字的主题名称")
        query = str(query).strip() or name
        if len(query) > 500 or len(str(domains)) > 2000:
            raise ValueError("检索词或域名列表过长")
        with self.lock, self.connect() as con:
            cur = con.execute("INSERT INTO topics(name,query,domains,created_at) VALUES(?,?,?,?)",
                              (name, query, str(domains).strip(), now()))
            topic_id = cur.lastrowid
        self.topic_dir(topic_id).mkdir(parents=True, exist_ok=True)
        return self.topic(topic_id)

    def topic_dir(self, topic_id):
        return self.root / "topics" / str(int(topic_id))

    def last_search(self, topic_id):
        path = self.topic_dir(topic_id) / "last_search.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None

    def sources(self, topic_id, included_only=False):
        self.topic(topic_id)
        with self.connect() as con:
            result = [json.loads(r[0]) for r in con.execute(
                "SELECT data FROM sources WHERE topic_id=? ORDER BY id", (topic_id,))]
        return [s for s in result if not s.get("excluded")] if included_only else result

    def source(self, source_id):
        with self.connect() as con:
            row = con.execute("SELECT data FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise ValueError("资料不存在")
        return json.loads(row[0])

    def save_source(self, topic_id, incoming, source_id=None):
        self.topic(topic_id)
        incoming = dict(incoming)
        for key in FIELDS:
            if key in incoming and key not in ("excluded", "verified"):
                incoming[key] = str(incoming[key] or "").strip()
        if not incoming.get("title"):
            raise ValueError("资料题名不能为空")
        if len(incoming.get("text", "")) > 2_000_000:
            raise ValueError("单篇提取文本超过 200 万字符，请分章节导入")
        incoming["doi"] = canonical_doi(incoming.get("doi", ""))
        incoming["isbn"] = re.sub(r"[ -]", "", incoming.get("isbn", ""))
        if incoming.get("url") and urlsplit(incoming["url"]).scheme not in ("http", "https"):
            raise ValueError("网址必须使用 http 或 https")
        if incoming.get("evidence_level", "metadata") not in LEVELS:
            raise ValueError("内容覆盖范围无效")
        with self.lock:
            existing = self.sources(topic_id)
            old = self.source(source_id) if source_id else next((s for s in existing if same_source(s, incoming)), None)
            if old and old["topic_id"] != topic_id:
                raise ValueError("资料不属于当前主题")
            if source_id and any(s["id"] != source_id and same_source(s, incoming) for s in existing):
                raise ValueError("该标识已对应本主题内的另一条资料")
            record = {key: "" for key in FIELDS}
            record.update({"kind": "article", "evidence_level": "metadata", "verified": False,
                           "excluded": False, "created_at": now(), "provenance": []})
            if old:
                record.update(old)
            updates = dict(incoming)
            if old and not source_id:
                updates = {k: v for k, v in updates.items() if v not in ("", None, [], False)}
                rank = {"metadata": 0, "abstract": 1, "excerpt": 2, "fulltext": 3}
                if rank.get(incoming.get("evidence_level"), 0) < rank.get(old["evidence_level"], 0) or (
                    incoming.get("evidence_level") == old["evidence_level"] and
                    len(incoming.get("text", "")) <= len(old.get("text", ""))):
                    updates.pop("text", None)
                    updates.pop("evidence_level", None)
                for k in ("summary", "main_content", "title_zh", "title_en", "verified", "excluded"):
                    if old.get(k):
                        updates.pop(k, None)
            provenance = updates.pop("provenance", [])
            updates.pop("id", None)
            updates.pop("topic_id", None)
            record.update(updates)
            record["provenance"] = record.get("provenance", []) + [p for p in provenance if p not in record.get("provenance", [])]
            record.update(id=old["id"] if old else "S" + uuid.uuid4().hex[:12], topic_id=topic_id, updated_at=now())
            if not record["text"]:
                record["evidence_level"] = "metadata"
            if not record["title_zh"] and re.search(r"[\u4e00-\u9fff]", record["title"]):
                record["title_zh"] = record["title"]
            if not record["title_en"] and not re.search(r"[\u4e00-\u9fff]", record["title"]):
                record["title_en"] = record["title"]
            record["ai_stale"] = bool(record.get("ai_based_on") and record["ai_based_on"] != digest(record))
            with self.connect() as con:
                con.execute("INSERT INTO sources VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                            (record["id"], topic_id, json.dumps(record, ensure_ascii=False)))
                con.execute("DELETE FROM chunks WHERE source_id=?", (record["id"],))
                if record["text"] and not record["excluded"]:
                    con.executemany("INSERT INTO chunks VALUES(?,?,?,?)", [
                        (record["id"], topic_id, i, text) for i, text in enumerate(chunks(record["text"]), 1)])
                con.execute("UPDATE topics SET revision=revision+1 WHERE id=?", (topic_id,))
            self.write_card(record)
        return record, old is None

    def write_card(self, source):
        s = source
        folder = self.topic_dir(s["topic_id"])
        fields = [("资料 ID", s["id"]), ("类型", s["kind"]), ("中文题名", s["title_zh"]),
                  ("英文题名", s["title_en"]), ("期刊 / 出版社 / 发布机构", s["venue"]),
                  ("作者", s["authors"]), ("作者单位（来源明确提供）", s["affiliations"]),
                  ("年份", s["year"]), ("DOI", s["doi"]), ("ISBN", s["isbn"]), ("网址", s["url"]),
                  ("内容覆盖范围", LEVELS[s["evidence_level"]]),
                  ("人工核验", "已核验" if s["verified"] else "待核验"),
                  ("纳入综述", "否" if s["excluded"] else "是"), ("获取时间 UTC", s["created_at"])]
        lines = [f"# {s['title']}", "", "## 基础信息", ""] + [f"- {k}：{v or '未提供'}" for k, v in fields]
        if s.get("original_file"):
            lines += [f"- 原始文件：[下载原件](../{s['original_file']})"]
        if s.get("ai_based_on"):
            lines += ["- 中文/英文译名与整理内容含 AI 生成内容，需对照原文核验。"]
        if s.get("ai_stale"):
            lines += ["- 原文或元数据已变化，上次 AI 整理内容已过期，请重新整理。"]
        metric = s.get("citation_metrics", {})
        if metric:
            count = metric.get("count")
            lines += [f"- 引用次数：{count if count is not None else '未提供'}（{metric.get('provider')}，{metric.get('retrieved_at')}）；不是期刊影响因子。"]
        if s.get("screening"):
            screening = s["screening"]
            lines += [f"- 自动筛选：{screening['mode']} / 候选集热度{screening['heat']} / {screening['path']}",
                      f"- 入选依据：{screening['reason']}（{screening['assessed_at']}）；不等于人工核验。"]
        if s.get("journal_metrics"):
            metric = s["journal_metrics"]
            lines += ([f"- 期刊 IF：{metric['value']}（{metric['year']}）；[核实来源]({metric['source_url']})；核实日期 {metric['retrieved_at']}。",
                       "- IF 是指定年份的期刊指标，不是本文发表时的 IF，也不是单篇论文质量分。"]
                      if metric.get("value") is not None else [f"- 期刊 IF：{metric['status']}（不记为0）。"])
        if s.get("importance"):
            priority = s["importance"]
            lines += [f"- 阅读重要度：{priority['score']} / 100；排名 {priority['rank'] or '未纳入'}。",
                      f"- 排序依据：{priority['reason']}。", f"- 排序规则：{priority['rule']}"]
        lines += ["", "## 一句话简介", "", s["summary"] or "尚未整理；请补充内容后运行 AI 整理。",
                  "", "## 主要内容", "", s["main_content"] or "尚未生成，以下保留可获得的原文。",
                  "", "## 备注", "", s["notes"] or "无", "", "## 来源记录", ""]
        lines += [f"- {p.get('provider', '')} | {p.get('url', '')} | {p.get('retrieved_at', '')}" for p in s["provenance"]]
        lines += ["", "## 原始摘要 / 提取文本", "", s["text"] or "未获取正文或摘要。"]
        atomic_text(folder / "sources" / f"{s['id']}.md", "\n".join(lines) + "\n")
        atomic_text(folder / "records" / f"{s['id']}.json", json.dumps(s, ensure_ascii=False, indent=2))

    def evidence(self, topic_id):
        with self.connect() as con:
            return [dict(r) for r in con.execute("SELECT * FROM chunks WHERE topic_id=? ORDER BY source_id,ordinal", (topic_id,))]

    def save_report(self, topic_id, kind, content, revision):
        if kind not in ("review", "direction"):
            raise ValueError("报告类型无效")
        with self.lock, self.connect() as con:
            con.execute("INSERT OR REPLACE INTO reports VALUES(?,?,?,?,?)", (topic_id, kind, revision, content, now()))
            atomic_text(self.topic_dir(topic_id) / "reports" / f"{kind}.md", content)

    def reports(self, topic_id):
        revision = self.topic(topic_id)["revision"]
        with self.connect() as con:
            return [{**dict(r), "stale": r["revision"] != revision} for r in con.execute(
                "SELECT * FROM reports WHERE topic_id=?", (topic_id,))]
