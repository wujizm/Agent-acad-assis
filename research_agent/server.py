import argparse
import base64
import binascii
import hashlib
import json
import mimetypes
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .collect import Collector, brief, extract_file, fetch_url, provenance, trusted_domains
from .config import Config, load_env
from .export import export_topic
from .intelligence import LLM, ResearchAgent
from .network import Network
from .store import FIELDS, Store

PROJECT = Path(__file__).resolve().parent.parent


class Jobs:
    def __init__(self):
        self.items = {}
        self.lock = threading.Lock()
        self.active = False

    def start(self, operation):
        with self.lock:
            if self.active:
                raise ValueError("已有任务正在运行，请等待当前任务结束")
            self.active = True
            job_id = uuid.uuid4().hex
            self.items[job_id] = {"id": job_id, "state": "running", "message": "任务开始", "result": None}
            if len(self.items) > 40:
                self.items.pop(next(iter(self.items)))

        def progress(message):
            with self.lock:
                self.items[job_id]["message"] = message

        def run():
            try:
                result = operation(progress)
                with self.lock:
                    self.items[job_id].update(state="done", message="任务完成", result=result)
            except Exception as exc:
                # No provider response bodies, URLs containing API keys, or local credentials in UI logs.
                message = str(exc) if isinstance(exc, ValueError) else f"任务未完成（{type(exc).__name__}），已保存的资料不受影响"
                with self.lock:
                    self.items[job_id].update(state="error", message=message)
            finally:
                with self.lock:
                    self.active = False

        threading.Thread(target=run, daemon=True).start()
        return {"job_id": job_id}

    def get(self, job_id):
        with self.lock:
            if job_id not in self.items:
                raise ValueError("任务不存在或服务已重启；请刷新资料列表")
            return dict(self.items[job_id])


class Application:
    def __init__(self, config):
        self.config = config
        self.store = Store(config.data_dir)
        self.config.load_model_settings()
        self.net = Network(config.contact_email)
        self.agent = ResearchAgent(self.store, LLM(config))
        self.collector = Collector(config, self.net, self.store, self.agent.llm)
        self.jobs = Jobs()
        self.csrf = secrets.token_urlsafe(24)

    def set_model(self, data):
        with self.jobs.lock:
            if self.jobs.active:
                raise ValueError("已有任务正在运行，请等任务结束后切换模型")
            self.config.save_model_settings(data)
            return self.config.public()

    def add_url(self, topic_id, url, progress, source_id=None):
        progress("正在读取网页或 PDF")
        incoming, payload, suffix = fetch_url(self.net, url)
        if source_id:
            old = self.store.source(source_id)
            # Refresh content, but retain curated bibliographic fields.
            incoming = {**incoming, **{k: old[k] for k in FIELDS if k not in
                ("text", "evidence_level", "summary", "main_content", "notes") and old.get(k)},
                "notes": old.get("notes", "") + "\n已从网址补充内容，提取结果待核验。",
                "provenance": old["provenance"] + incoming["provenance"]}
        record, created = self.store.save_source(topic_id, incoming, source_id)
        relative = f"originals/{record['id']}-{uuid.uuid4().hex[:8]}{suffix}"
        path = self.store.topic_dir(topic_id) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        record["original_file"] = relative
        self.store.save_source(topic_id, record, record["id"])
        return {"source_id": record["id"], "created": created}

    def upload(self, topic_id, data, progress):
        filename = Path(str(data.get("filename", ""))).name
        if not filename.lower().endswith((".pdf", ".txt", ".md")):
            raise ValueError("只接受 PDF、TXT、Markdown")
        try:
            payload = base64.b64decode(data.get("content", ""), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("上传文件编码错误") from exc
        if not payload or len(payload) > 20_000_000:
            raise ValueError("文件为空或超过 20 MB")
        progress("正在提取文件文本")
        text, meta = extract_file(payload, filename)
        incoming = {"title": data.get("title") or meta.get("title") or Path(filename).stem,
                    "kind": data.get("kind", "other"), "authors": meta.get("author", ""), "text": text,
                    "evidence_level": data.get("evidence_level", "fulltext"), "summary": brief(text),
                    "notes": "用户上传：" + filename + "。自动提取的题名、作者及内容范围待核验。",
                    "provenance": provenance("用户上传", ""), "raw_metadata": meta,
                    "file_sha256": hashlib.sha256(payload).hexdigest()}
        record, created = self.store.save_source(topic_id, incoming)
        relative = f"originals/{record['id']}-{uuid.uuid4().hex[:8]}{Path(filename).suffix.lower()}"
        target = self.store.topic_dir(topic_id) / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        record["original_file"] = relative
        self.store.save_source(topic_id, record, record["id"])
        return {"source_id": record["id"], "created": created}


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Avoid persisting source URLs or research questions in access logs.
            pass

        def send(self, payload, status=200, content_type="application/json; charset=utf-8", filename=None):
            if not isinstance(payload, bytes):
                payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(payload)

        def allowed_host(self):
            host = self.headers.get("Host", "")
            return host in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            try:
                if not self.allowed_host():
                    self.send({"error": "仅接受本机访问"}, 403)
                    return
                path = unquote(urlsplit(self.path).path)
                parts = path.strip("/").split("/")
                if path == "/api/status":
                    self.send({**app.config.public(), "csrf": app.csrf})
                elif path == "/license":
                    self.send((PROJECT / "LICENSE").read_bytes(), content_type="text/plain; charset=utf-8")
                elif path == "/api/topics":
                    self.send(app.store.topics())
                elif len(parts) == 3 and parts[:2] == ["api", "topics"]:
                    topic_id = int(parts[2])
                    sources = [{**{k: v for k, v in s.items() if k not in ("text", "raw_metadata")},
                                "text_length": len(s["text"])} for s in app.store.sources(topic_id)]
                    self.send({"topic": app.store.topic(topic_id), "sources": sources, "reports": app.store.reports(topic_id),
                               "last_search": app.store.last_search(topic_id)})
                elif len(parts) == 3 and parts[:2] == ["api", "sources"]:
                    self.send(app.store.source(parts[2]))
                elif len(parts) == 3 and parts[:2] == ["api", "jobs"]:
                    self.send(app.jobs.get(parts[2]))
                elif len(parts) == 4 and parts[:2] == ["api", "topics"] and parts[3] == "export":
                    topic_id = int(parts[2])
                    fmt = parse_qs(urlsplit(self.path).query).get("format", ["zip"])[0]
                    if fmt not in ("xlsx", "zip"):
                        raise ValueError("导出格式无效")
                    xlsx, archive = export_topic(app.store, topic_id)
                    self.send(xlsx if fmt == "xlsx" else archive, content_type=(
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if fmt == "xlsx" else "application/zip"),
                        filename=f"topic-{topic_id}.{fmt}")
                elif len(parts) >= 4 and parts[0] == "files":
                    root = app.store.topic_dir(int(parts[1])).resolve()
                    file = (root / "/".join(parts[2:])).resolve()
                    if not file.is_relative_to(root) or not file.is_file():
                        raise ValueError("文件不存在")
                    self.send(file.read_bytes(), content_type="application/octet-stream", filename="source" + file.suffix)
                elif path in ("/", "/app.js", "/style.css"):
                    file = PROJECT / "static" / ("index.html" if path == "/" else path.lstrip("/"))
                    self.send(file.read_bytes(), content_type=(mimetypes.guess_type(str(file))[0] or "text/plain") + "; charset=utf-8")
                else:
                    self.send({"error": "未找到"}, 404)
            except (ValueError, TypeError) as exc:
                self.send({"error": str(exc)}, 400)
            except (ConnectionAbortedError, BrokenPipeError):
                pass
            except Exception as exc:
                self.send({"error": f"服务错误（{type(exc).__name__}）"}, 500)

        def do_POST(self):
            try:
                origin = self.headers.get("Origin")
                allowed = (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}")
                if not self.allowed_host() or (origin and origin not in allowed) or self.headers.get("X-CSRF-Token") != app.csrf:
                    self.send({"error": "请求来源无效，请刷新本地页面"}, 403)
                    return
                if not self.headers.get("Content-Type", "").startswith("application/json"):
                    raise ValueError("需要 JSON 请求")
                length = int(self.headers.get("Content-Length", 0))
                if length < 1 or length > 28_000_000:
                    self.send({"error": "请求为空或超过大小限制"}, 413)
                    return
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("请求必须为 JSON 对象")
                parts = urlsplit(self.path).path.strip("/").split("/")
                if parts == ["api", "model-settings"]:
                    result = app.set_model(data)
                elif parts == ["api", "model-test"]:
                    def check_model(progress):
                        progress("正在测试模型连接")
                        return app.agent.llm.check_connection()
                    result = app.jobs.start(check_model)
                elif parts == ["api", "topics"]:
                    trusted_domains(str(data.get("domains", "")))
                    result = app.store.create_topic(data.get("name", ""), data.get("query", ""), data.get("domains", ""))
                elif len(parts) == 4 and parts[:2] == ["api", "topics"]:
                    topic_id, action = int(parts[2]), parts[3]
                    app.store.topic(topic_id)
                    if action == "collect":
                        result = app.jobs.start(lambda p: app.collector.run(topic_id, data.get("limit", 10), p, data.get("mode", "auto")))
                    elif action == "enrich":
                        result = app.jobs.start(lambda p: app.agent.enrich(topic_id, p))
                    elif action == "rank":
                        result = app.jobs.start(lambda p: app.collector.rerank(topic_id))
                    elif action == "report":
                        result = app.jobs.start(lambda p: app.agent.report(topic_id, data.get("kind", "review"), p))
                    elif action == "ask":
                        result = app.jobs.start(lambda p: app.agent.ask(topic_id, data.get("question", ""), data.get("use_ai", True)))
                    elif action == "url":
                        result = app.jobs.start(lambda p: app.add_url(topic_id, data.get("url", ""), p))
                    elif action == "upload":
                        result = app.jobs.start(lambda p: app.upload(topic_id, data, p))
                    elif action == "sources":
                        incoming = {k: v for k, v in data.items() if k in FIELDS}
                        incoming["provenance"] = provenance("用户手工录入", incoming.get("url", ""))
                        result = app.store.save_source(topic_id, incoming)[0]
                    else:
                        raise ValueError("不支持的操作")
                elif len(parts) in (3, 4) and parts[:2] == ["api", "sources"]:
                    source = app.store.source(parts[2])
                    if len(parts) == 4 and parts[3] == "fetch":
                        result = app.jobs.start(lambda p: app.add_url(source["topic_id"], source["url"], p, source["id"]))
                    elif len(parts) == 3:
                        source.update({k: v for k, v in data.items() if k in FIELDS})
                        result = app.store.save_source(source["topic_id"], source, source["id"])[0]
                    else:
                        raise ValueError("不支持的操作")
                else:
                    self.send({"error": "未找到"}, 404)
                    return
                self.send(result)
            except (ValueError, TypeError, KeyError) as exc:
                self.send({"error": str(exc)}, 400)
            except (ConnectionAbortedError, BrokenPipeError):
                pass
            except Exception as exc:
                self.send({"error": f"服务错误（{type(exc).__name__}）"}, 500)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="材料学资料整理 Agent（仅本机）")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=PROJECT / "data")
    args = parser.parse_args()
    load_env(PROJECT / ".env")
    app = Application(Config.from_env(args.data_dir))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(app))
    print(f"Research library: http://127.0.0.1:{server.server_port}", flush=True)
    print(f"Local data: {app.store.root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
