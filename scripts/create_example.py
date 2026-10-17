"""Create the public AI for Science tutorial in a new local data directory, offline."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from research_agent.config import Config
from research_agent.export import export_topic
from research_agent.intelligence import LLM, ResearchAgent
from research_agent.screening import rank_sources
from research_agent.store import Store

EXAMPLE = ROOT / "examples" / "ai-for-science"


def create_example(data_dir):
    data_dir = Path(data_dir).resolve()
    if data_dir.exists() and (not data_dir.is_dir() or any(data_dir.iterdir())):
        raise ValueError("示例需要新的空目录；请换一个 --data-dir，不会覆盖已有资料。")
    inputs = json.loads((EXAMPLE / "sources.json").read_text(encoding="utf-8"))
    store = Store(data_dir)
    topic = store.create_topic("AI for Science · 入门示例", inputs["query"], inputs["domains"])
    for item in inputs["sources"]:
        record = dict(item)
        note = record.pop("note_file", None)
        if note:
            text = (EXAMPLE / note).read_text(encoding="utf-8")
            relative = "originals/" + Path(note).name
            original = store.topic_dir(topic["id"]) / relative
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_text(text, encoding="utf-8")
            record.update(text=text, original_file=relative)
        store.save_source(topic["id"], record)
    for record in rank_sources(store.sources(topic["id"]), inputs["query"]):
        store.save_source(topic["id"], record, record["id"])
    # No environment configuration is loaded and no model/network operation is performed.
    agent = ResearchAgent(store, LLM(Config(data_dir)))
    question = "材料预测稳定是否等于已经实验合成？"
    answer = agent.ask(topic["id"], question, use_ai=False)
    (data_dir / "offline-qa.json").write_text(json.dumps(answer, ensure_ascii=False, indent=2), encoding="utf-8")
    _, archive = export_topic(store, topic["id"])
    bundle = store.topic_dir(topic["id"]) / "主题资料包.zip"
    bundle.write_bytes(archive)
    result = {"topic_id": topic["id"], "sources": len(store.sources(topic["id"])),
              "sources_with_text": sum(bool(s["text"]) for s in store.sources(topic["id"])),
              "question": question, "evidence_count": len(answer["evidence"]),
              "reports_generated": 0, "model_calls": 0,
              "data_dir": str(data_dir), "bundle": str(bundle)}
    (data_dir / "demo-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".test-output" / "ai-for-science-demo")
    args = parser.parse_args()
    try:
        result = create_example(args.data_dir)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
