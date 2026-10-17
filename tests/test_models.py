import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from research_agent.config import Config
from research_agent.intelligence import LLM
from research_agent.server import Application


class ModelBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_switch_is_persistent_and_preserves_api_configuration(self):
        config = Config(self.root, llm_base_url="https://api.example/v1",
                        llm_model="api-model", llm_api_key="private-test-key")
        app = Application(config)
        app.set_model({"llm_backend": "codex", "codex_model": "chosen-model"})
        saved = json.loads((self.root / "model-settings.json").read_text())
        self.assertEqual(saved, {"llm_backend": "codex", "codex_model": "chosen-model"})
        restarted = Application(Config(self.root))
        self.assertEqual(restarted.config.llm_backend, "codex")
        self.assertEqual(restarted.config.codex_model, "chosen-model")
        app.set_model({"llm_backend": "api", "codex_model": "chosen-model"})
        self.assertEqual(config.llm_api_key, "private-test-key")
        self.assertEqual(config.public()["model"], "api-model")
        self.assertNotIn("private-test-key", json.dumps(config.public()))

    def test_invalid_or_busy_switch_does_not_change_configuration(self):
        app = Application(Config(self.root))
        with self.assertRaises(ValueError):
            app.set_model({"llm_backend": "unknown"})
        app.jobs.active = True
        with self.assertRaisesRegex(ValueError, "任务"):
            app.set_model({"llm_backend": "codex"})
        self.assertEqual(app.config.llm_backend, "api")
        self.assertFalse((self.root / "model-settings.json").exists())

    def test_codex_reads_only_final_output_and_keeps_prompt_out_of_arguments(self):
        config = Config(self.root, llm_backend="codex", codex_model="chosen-model")
        prompt = '原文中文；$(不执行) & "引号"'
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            final = Path(command[command.index("--output-last-message") + 1])
            final.write_text(json.dumps({"content": '{"summary":"中文结果"}'}, ensure_ascii=False), encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, "忽略过程日志", "")

        with patch("research_agent.config.shutil.which", return_value="C:/tools/codex.exe"), \
                patch("research_agent.codex_model.subprocess.run", side_effect=run):
            result = LLM(config).complete(prompt, json_output=True)
        self.assertEqual(result, {"summary": "中文结果"})
        command, kwargs = calls[0]
        self.assertNotIn(prompt, command)
        self.assertIn(prompt, kwargs["input"])
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
        self.assertIn("features.shell_tool=false", command)
        self.assertIn("web_search=\"disabled\"", command)
        self.assertIn("--ignore-user-config", command)
        self.assertIn("--ephemeral", command)
        self.assertIn("chosen-model", command)

    def test_codex_missing_timeout_and_error_are_actionable_without_raw_logs(self):
        config = Config(self.root, llm_backend="codex")
        with patch("research_agent.config.shutil.which", return_value=None):
            with self.assertRaisesRegex(ValueError, "Codex CLI"):
                LLM(config).complete("测试")
        with patch("research_agent.config.shutil.which", return_value="C:/tools/codex.exe"):
            with patch("research_agent.codex_model.subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 300)):
                with self.assertRaisesRegex(ValueError, "超时"):
                    LLM(config).complete("测试")
            failure = subprocess.CompletedProcess([], 1, "", "401 Unauthorized secret-do-not-display")
            with patch("research_agent.codex_model.subprocess.run", return_value=failure):
                with self.assertRaisesRegex(ValueError, "codex login") as caught:
                    LLM(config).complete("测试")
            self.assertNotIn("secret-do-not-display", str(caught.exception))

    def test_codex_partial_or_invalid_output_is_rejected(self):
        config = Config(self.root, llm_backend="codex")
        for value, code in [("partial", 0), ('{"content":""}', 0), ('{"content":"looks valid"}', 1)]:
            with self.subTest(value=value, code=code):
                def run(command, **kwargs):
                    Path(command[command.index("--output-last-message") + 1]).write_text(value, encoding="utf-8")
                    return subprocess.CompletedProcess(command, code, "", "")
                with patch("research_agent.config.shutil.which", return_value="C:/tools/codex.exe"), \
                        patch("research_agent.codex_model.subprocess.run", side_effect=run):
                    with self.assertRaises(ValueError):
                        LLM(config).complete("测试")

    def test_default_still_uses_api_after_switching_back(self):
        config = Config(self.root, llm_base_url="https://api.example/v1", llm_model="external", llm_api_key="private")
        app = Application(config)
        app.set_model({"llm_backend": "codex"})
        app.set_model({"llm_backend": "api"})
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": "API 正常"}, "finish_reason": "stop"}]}
        with patch("research_agent.intelligence.requests.post", return_value=response) as post:
            self.assertEqual(app.agent.llm.complete("测试"), "API 正常")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer private")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "external")


if __name__ == "__main__":
    unittest.main()
