"""Explicit live validation of the three requested topics; uses network and Codex quota."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from research_agent.config import Config, load_env
from research_agent.export import export_topic
from research_agent.server import Application
from research_agent.store import atomic_text

TOPICS = ["AI for Science", "机器学习势函数", "金属导电理论"]
QUESTIONS = {
    "AI for Science": "根据已收集原文，AI for Science 的主要路线和验证局限是什么？请区分已报告的进展与展望。",
    "机器学习势函数": "根据已收集原文，机器学习原子间势的主要方法路线是什么？如何验证精度、适用域及外推风险？",
    "金属导电理论": "根据已收集原文，金属导电理论中的经典输运与量子处理有哪些联系和适用限制？哪些问题现有证据不能回答？"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["collect", "finish"])
    parser.add_argument("--topic", choices=TOPICS)
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()
    load_env(PROJECT / ".env")
    app = Application(Config.from_env(PROJECT / "data"))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    for name in ([args.topic] if args.topic else TOPICS):
        topic = next((t for t in app.store.topics() if t["name"] == name), None) or app.store.create_topic(name)
        topic_id = topic["id"]
        folder = app.store.topic_dir(topic_id)
        print(f"TOPIC {topic_id}: {name}", flush=True)
        progress = lambda message: print(message, flush=True)
        result = {"topic": name, "topic_id": topic_id, "stage": args.stage, "time": timestamp}
        if args.stage == "collect":
            if app.store.sources(topic_id):
                _, backup = export_topic(app.store, topic_id)
                (folder / f"before-rerun-{timestamp}.zip").write_bytes(backup)
            result["collection"] = app.collector.run(topic_id, args.limit, progress)
        else:
            app.collector.rerank(topic_id)
            result["enrichment"] = app.agent.enrich(topic_id, progress)
            if result["enrichment"]["warnings"]:
                print(json.dumps(result["enrichment"], ensure_ascii=False), flush=True)
            for kind in ("review", "direction"):
                result[kind] = app.agent.report(topic_id, kind, progress)
                atomic_text(folder / f"validation-{args.stage}.json", json.dumps(result, ensure_ascii=False, indent=2))
            progress("正在验证知识库问答")
            result["qa"] = app.agent.ask(topic_id, QUESTIONS[name])
            if result["qa"]["mode"] != "ai":
                raise ValueError("未生成有证据的 AI 回答")
        records = app.store.sources(topic_id, included_only=True)
        result["counts"] = {"included": len(records), "with_text": sum(bool(s["text"]) for s in records),
                            "with_if": sum(s.get("journal_metrics", {}).get("value") is not None for s in records)}
        atomic_text(folder / f"validation-{args.stage}.json", json.dumps(result, ensure_ascii=False, indent=2))
        if args.stage == "finish":
            _, bundle = export_topic(app.store, topic_id)
            (folder / "主题资料包.zip").write_bytes(bundle)
        print(json.dumps(result["counts"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
