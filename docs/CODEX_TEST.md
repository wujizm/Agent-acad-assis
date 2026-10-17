# 本机 Codex 接入验证

日期：2026-10-17（Asia/Shanghai）。CLI：`0.163.0-alpha.10.2`。官方 CLI 报告登录方式为 ChatGPT；未读取或复制登录凭据。此次使用 CLI 内置默认模型，未指定模型名。

## 已完成的验证

- 45 项自动化测试通过，JavaScript 语法检查通过。覆盖原有 API、模型切换持久化、API 密钥保留、任务期间禁止切换、CSRF、Codex 输入及输出处理、超时和异常输出。
- 真实 CLI 连接成功，收到“连接成功”文本。
- 网页“保存并测试连接”真实调用成功；API / Codex 两种模式均能保存切换，最终选择 Codex。
- 在网页 AI for Science 主题中实际提交“co-pilot 到 lab-pilot”的问题，收到中文回答，引用正确指向正式资料 `S57b7ee2f3839:C1` / `C2`，并说明缺少量化验证。
- 本机 Codex 位于桌面应用提供的路径，未加入系统持久 PATH；已在本项目 `.env` 写入非敏感的原生程序路径，便于从独立终端重启。没有新增或改动 API 密钥。
- 用已有 AI for Science 文献的副本运行单篇整理与问答。原资料库未被测试脚本修改。

## 真实资料与结果检查

资料：Thomas Hartung，2025，*AI, agentic models and lab automation for scientific discovery — the beginning of scAInce*。原资料 ID：`S57b7ee2f3839`。来源：[DOI](https://doi.org/10.3389/frai.2025.1649155)。本次只使用已收集的 1636 字符摘要，不包含全文。

单篇整理耗时约 21.7 秒，生成中英文题名、一句话简介与主要内容。逐项对照摘要：多模态智能体、文献综合与假设生成、自驱动实验室、“co-pilot 到 lab-pilot”的转变及可重复性/审计/安全/公平获取等内容均有摘要依据。输出标明“未获取全文”，没有补写作者单位、实验指标或效率提升数字。

问答（含检索词扩展）耗时约 43.0 秒，使用两个原文片段。输出引用通过编号检查，内容能对应摘要；将作者的趋势判断与经过实验验证的结果区分，并说明无法从摘要确定自主程度、具体性能和治理成效。

完整原文、生成结果、片段与用时记录保存在本机 `.test-output/codex-live/20261016-172541/`，这些个人测试文件不随源码发布。测试副本的资料 ID 独立于正式资料库，引用以实际运行结果中的证据编号为准。可公开复现的输入、操作和预期检查见 [AI for Science 标准教程](../examples/ai-for-science/README.md)；重新测试自己的资料时可按主 README 运行 `scripts/check_codex.py`。

## 验证范围

真实调用验证了 Codex 连接、单篇整理和问答。综述与方向总结复用同一模型适配器，已有自动化引用/保存回归测试；本次没有重新生成全主题报告。API 分支使用模拟接口做回归，未配置新的外部 API 密钥或进行远程供应商实测。一次摘要测试不代表所有主题和模型输出均无需核验。

CLI 本身在本机执行，模型仍由 OpenAI 云端提供；此接入不是离线推理。官方行为依据：[非交互调用](https://learn.chatgpt.com/docs/non-interactive-mode)、[认证方式](https://learn.chatgpt.com/docs/auth)。
