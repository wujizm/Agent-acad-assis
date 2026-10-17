"""Opt-in live Codex check using one existing source; consumes Codex quota."""
import argparse
import json
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from research_agent.config import Config, load_env
from research_agent.intelligence import LLM, ResearchAgent, validate_citations
from research_agent.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-id", required=True, help="Existing source with abstract or full text")
    parser.add_argument("--data-dir", type=Path, default=PROJECT / "data")
    parser.add_argument("--question", required=True, help="Question grounded in the selected source")
    args = parser.parse_args()
    load_env(PROJECT / ".env")
    config = Config.from_env(args.data_dir)
    config.load_model_settings()
    config.llm_backend = "codex"
    original_store = Store(args.data_dir)
    source = original_store.source(args.source_id)
    if source["excluded"] or not source["text"]:
        raise ValueError("请选择已纳入且包含原始文本的资料")
    output = PROJECT / ".test-output" / "codex-live" / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    output.mkdir(parents=True)
    result = {"source_id": source["id"], "title": source["title"], "url": source["url"],
              "evidence_level": source["evidence_level"], "original_text": source["text"],
              "model": config.public()["model"], "question": args.question}

    def save():
        (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="research-codex-test-") as directory:
        store = Store(Path(directory))
        topic = store.create_topic(original_store.topic(source["topic_id"])["name"])
        copied = {k: v for k, v in source.items() if k not in ("ai_based_on", "original_file")}
        record, _ = store.save_source(topic["id"], copied)
        agent = ResearchAgent(store, LLM(config))
        started = time.monotonic()
        enrichment = agent.enrich(topic["id"], lambda _: print("Enriching one real source...", flush=True))
        if enrichment["updated"] != 1 or enrichment["warnings"]:
            raise ValueError(str(enrichment))
        enriched = store.source(record["id"])
        assert enriched["text"] == source["text"]
        assert enriched["authors"] == source["authors"] and enriched["affiliations"] == source["affiliations"]
        result["enrichment"] = {k: enriched[k] for k in ("title_zh", "title_en", "summary", "main_content")}
        result["enrichment_seconds"] = round(time.monotonic() - started, 1)
        (output / "source.md").write_bytes((store.topic_dir(topic["id"]) / "sources" / f"{record['id']}.md").read_bytes())
        save()
        print("Enrichment passed; checking retrieval and cited answer...", flush=True)
        started = time.monotonic()
        answer = agent.ask(topic["id"], args.question)
        if answer["mode"] != "ai" or answer["warnings"]:
            raise ValueError(str(answer))
        validate_citations(answer["answer"], [e["label"] for e in answer["evidence"]])
        result["qa"] = answer
        result["qa_seconds"] = round(time.monotonic() - started, 1)
        result["original_library_unchanged"] = original_store.source(source["id"]) == source
        assert result["original_library_unchanged"]
        save()
    print("PASS: " + str(output / "result.json"), flush=True)


if __name__ == "__main__":
    main()
