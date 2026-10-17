"""Text-only Codex CLI bridge; authentication remains owned by the official CLI."""

import json
import os
import subprocess
import tempfile
from pathlib import Path


def complete(config, system, prompt):
    executable = config.codex_executable
    if not executable:
        raise ValueError("未找到 Codex CLI：请安装官方 CLI，或在 .env 中设置 CODEX_COMMAND 为 codex.exe 的完整路径，然后重启")
    # An envelope works for both prose and JSON requested by the existing agent.
    schema = {"type": "object", "properties": {"content": {"type": "string"}},
              "required": ["content"], "additionalProperties": False}
    with tempfile.TemporaryDirectory(prefix="research-codex-") as directory:
        root = Path(directory)
        schema_path, output_path = root / "schema.json", root / "answer.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        command = [executable, "--no-daemon", "-a", "never", "exec",
                   "--ignore-user-config", "--skip-git-repo-check", "--ephemeral",
                   "--sandbox", "read-only", "--cd", str(root), "--color", "never",
                   "--output-schema", str(schema_path), "--output-last-message", str(output_path)]
        # Overrides apply only to this child process, not the user's Codex settings.
        for option in ('web_search="disabled"', 'project_doc_max_bytes=0',
                       'features.shell_tool=false', 'features.unified_exec=false',
                       'features.shell_snapshot=false', 'features.apps=false',
                       'features.plugins=false', 'features.hooks=false',
                       'features.browser_use=false', 'features.computer_use=false',
                       'features.multi_agent=false', 'features.memories=false',
                       'features.skill_search=false', 'features.view_image=false'):
            command.extend(["-c", option])
        if config.codex_model:
            command.extend(["--model", config.codex_model])
        command.append("-")
        env = os.environ.copy()
        for key in ("LLM_API_KEY", "OPENALEX_API_KEY", "BRAVE_SEARCH_API_KEY", "OPENAI_API_KEY", "CODEX_API_KEY"):
            env.pop(key, None)
        instruction = (system + "\n这是资料库中的一次纯文本处理。禁止调用工具或读取其他文件；直接完成输入任务。"
                       "最终输出为符合 schema 的对象，将完整答案放在 content 字符串中。"
                       "如果任务要求 JSON，将该 JSON 对象序列化为 content 的字符串值。\n\n任务与证据：\n" + prompt)
        try:
            result = subprocess.run(command, input=instruction, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace", timeout=300, cwd=root, env=env,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Codex 调用超时（5 分钟），已终止本次调用；请缩短输入或稍后重试，原始资料仍在本地") from exc
        except OSError as exc:
            raise ValueError("无法启动 Codex CLI；请检查 CODEX_COMMAND 和本机执行权限") from exc
        if result.returncode:
            # Never expose CLI logs, which may contain prompts or credential-related details.
            detail = (result.stderr + result.stdout).casefold()
            if any(word in detail for word in ("not logged in", "unauthorized", "401", "refresh token", "authentication")):
                raise ValueError("Codex 登录无效：请在本机终端运行 codex login，完成官方登录后重试")
            if any(word in detail for word in ("usage limit", "rate limit", "quota", "429")):
                raise ValueError("Codex 额度或速率受限；请等待额度恢复，或在设置中切换至模型 API")
            if any(word in detail for word in ("unexpected argument", "unknown feature", "unrecognized")):
                raise ValueError("Codex CLI 版本不支持所需参数；请更新官方 CLI 后重试")
            raise ValueError(f"Codex 调用失败（退出码 {result.returncode}）；请检查登录、所选模型、网络或额度后重试")
        try:
            value = json.loads(output_path.read_text(encoding="utf-8"))
            content = value.get("content") if isinstance(value, dict) else None
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty")
            return content.strip()
        except (OSError, ValueError) as exc:
            raise ValueError("Codex 未返回完整的结构化答案，未保存本次结果；请重试") from exc
