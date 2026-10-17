"""Read-only checks against public metadata services; no model calls or private data."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from research_agent.collect import crossref_record, book_record
from research_agent.network import Network

net = Network()
checks = [
    ("Crossref", "https://api.crossref.org/works", {"query.bibliographic": "high entropy alloys", "rows": 1},
     lambda d: crossref_record(d["message"]["items"][0])),
    ("Open Library", "https://openlibrary.org/search.json", {"q": "materials science", "limit": 1,
     "fields": "key,title,author_name,first_publish_year,publisher"}, lambda d: book_record(d["docs"][0]))]
failed = False
for name, url, params, convert in checks:
    try:
        record = convert(net.json(url, params))
        print(name, "OK", record["title"], flush=True)
    except Exception as exc:
        failed = True
        print(name, "FAILED", str(exc), flush=True)
sys.exit(1 if failed else 0)
