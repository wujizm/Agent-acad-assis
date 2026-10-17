"""Dated JIF observations from publisher pages; never substitute CiteScore."""
import json
import re
from pathlib import Path


CATALOG = Path(__file__).resolve().parent.parent / "resources" / "journal_metrics.json"


def journal_metric(record, catalog=None):
    if record.get("kind") != "article" or record.get("record_type") == "proceedings-article":
        return {"status": "不适用", "value": None}
    if catalog is None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else []
    normalize = lambda value: re.sub(r"[\W_]", "", value.casefold())
    name = normalize(record.get("venue", ""))
    issns = set(record.get("issn", []))
    matches = [m for m in catalog if (issns & set(m.get("issn", []))) or
               name in {normalize(n) for n in [m["journal"], *m.get("aliases", [])]}]
    if not matches:
        return {"status": "未核实", "value": None}
    metric = max(matches, key=lambda m: m["year"])
    return {**metric, "status": "已核实", "metric": "Journal Impact Factor",
            "note": "指定年份的期刊指标，不是本文发表时的 IF，也不是单篇论文质量分。"}
