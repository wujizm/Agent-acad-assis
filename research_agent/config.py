import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


def load_env(path: Path):
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


@dataclass
class Config:
    data_dir: Path
    llm_base_url: str = ""
    llm_model: str = ""
    llm_api_key: str = ""
    openalex_api_key: str = ""
    brave_search_api_key: str = ""
    contact_email: str = ""
    llm_backend: str = "api"
    codex_command: str = "codex"
    codex_model: str = ""

    @classmethod
    def from_env(cls, data_dir: Path):
        config = cls(data_dir=data_dir, **{name: os.getenv(name.upper(), field.default)
                                        for name, field in cls.__dataclass_fields__.items() if name != "data_dir"})
        config.model_options({"llm_backend": config.llm_backend, "codex_model": config.codex_model})
        return config

    @property
    def codex_executable(self):
        executable = shutil.which(self.codex_command or "codex")
        # Native executables avoid Windows batch-file argument interpretation.
        if executable and Path(executable).suffix.lower() not in (".cmd", ".bat", ".ps1"):
            return executable
        return None

    @property
    def api_ready(self):
        return bool(self.llm_base_url and self.llm_model)

    @property
    def llm_ready(self):
        return bool(self.codex_executable) if self.llm_backend == "codex" else self.api_ready

    def model_options(self, data):
        backend = data.get("llm_backend", self.llm_backend)
        model = data.get("codex_model", self.codex_model)
        if backend not in ("api", "codex"):
            raise ValueError("模型接入方式只能是 api 或 codex")
        if not isinstance(model, str) or len(model) > 120 or any(c in model for c in "\r\n\x00"):
            raise ValueError("Codex 模型名称应为不超过 120 字符的单行文字")
        return {"llm_backend": backend, "codex_model": model.strip()}

    def load_model_settings(self):
        path = self.data_dir / "model-settings.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("设置应为对象")
                options = self.model_options(data)
            except (ValueError, TypeError) as exc:
                raise ValueError("data/model-settings.json 中的模型设置无效，请检查后重启") from exc
            self.llm_backend, self.codex_model = options["llm_backend"], options["codex_model"]

    def save_model_settings(self, data):
        options = self.model_options(data)
        path = self.data_dir / "model-settings.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(options, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        self.llm_backend, self.codex_model = options["llm_backend"], options["codex_model"]

    def public(self):
        return {"llm_ready": self.llm_ready, "llm_backend": self.llm_backend,
                "model": (self.codex_model or "CLI 默认模型") if self.llm_backend == "codex" else self.llm_model,
                "codex_available": bool(self.codex_executable), "codex_model": self.codex_model,
                "api_ready": self.api_ready, "api_model": self.llm_model,
                "openalex_ready": bool(self.openalex_api_key),
                "web_search_ready": bool(self.brave_search_api_key)}
