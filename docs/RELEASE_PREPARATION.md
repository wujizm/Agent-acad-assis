# 发布准备说明

日期：2026-10-17。项目按本地个人工具的实验版准备；这份说明不代表已经创建或上传 GitHub 仓库。

## 许可证与分发范围

项目原创代码及原创教程采用 **AGPL-3.0-only**，见 [LICENSE](../LICENSE) 和 [第三方依赖声明](../THIRD_PARTY_NOTICES.md)。网页提供许可全文入口。发布修改版及提供网络服务时，应按许可证履行相应声明、源码和修改说明义务。

公开内容包括源码、依赖清单、测试、文档、许可声明、公开指标快照及 `examples/ai-for-science` 中的书目信息和原创教学材料。`.env`、`.env.*`（`.env.example` 除外）、`data/`、`.test-output/`、虚拟环境和日志保持排除。旧测试文档保留历史结果，但不再链接这些被排除的个人文件。

## 资料抓取修复

原实现只确认 DNS 结果里存在公网地址，然后让 HTTP 客户端自行连接域名。修复后先筛出公网单播地址，再将 HTTP 连接绑定到这些数值 IP。混合公网/内网结果只允许使用经过验证的公网地址；没有可用公网地址时拒绝访问。

HTTPS 保留原域名的 Host、SNI 和证书校验。每次跳转重新解析并验证，跳转时移除调用方鉴权头；连接失败只回退到同批已验证地址。保留超时、最多 6 次请求和解压后大小限制。

**代理边界：**资料抓取不隐式使用系统或环境变量代理，也不读取 `.netrc` 凭据，以避免代理端重新解析目标绕过本地校验。依赖 HTTP/SOCKS 代理才能联网的环境需要另行适配；可以先下载有权使用的资料再上传。系统级 TUN/VPN 的行为由系统控制。本次在当前网络中验证了 Crossref、Open Library 以及公开 PDF 下载与文字提取。模型 API 的独立调用不使用这个资料抓取模块。

测试覆盖混合 IPv4/IPv6、解析后连接绑定、内网和特殊地址、IPv6 回退、跳转到内网、跳转时鉴权头清除、代理绕过、证书失败、解压大小限制及公开网页读取。这是针对已发现问题的修复和回归检查，不是完整安全审计或公网服务认证。

## 可复现的示例

从 [AI for Science 标准教程](../examples/ai-for-science/README.md) 开始。`scripts/create_example.py` 创建独立空目录，拒绝覆盖已有资料，不读取 `.env`，不联网、不调用模型。输入为 3 条论文书目、1 条书籍书目、1 条机构网页书目和 3 篇原创教学笔记。

脚本调用项目自身的存储、排序、检索和导出功能，生成 8 份资料卡、Excel、ZIP 及离线检索结果。初始报告为 0；附带的两篇范文明确是教学说明，不是模型运行记录。联网、真实模型生成和证据复核步骤另有说明，结果允许随来源及模型变化。

## 依赖与兼容性

`requirements.txt` 声明允许的依赖范围；[constraints-tested.txt](../constraints-tested.txt) 记录此次独立环境验证使用的直接和间接依赖版本。需要复现时同时使用两者：

```powershell
python -m pip install -r requirements.txt -c constraints-tested.txt
python -m pip check
python -m unittest discover -s tests -v
node --check static/app.js
python scripts/check_docs.py
python scripts/create_example.py --data-dir .test-output/new-example
```

`new-example` 应为新的空目录，测试不会清空已有目录。文档检查离线检查 Markdown 文件目标和私有目录引用，不验证外部网址可达性或段落锚点。

| 环境 / 功能 | 验证范围 |
| --- | --- |
| Windows / Python 3.13.7 | 排除个人配置与资料的公开源码副本中，67 项自动化测试通过；依赖检查、JS 语法、41 个本地文档链接检查和离线示例生成通过。网络专项 11 项还在 urllib3 2.6.3 环境通过 |
| Windows、Ubuntu / Python 3.11、3.13 | 已配置 GitHub Actions 矩阵；仓库发布后才会实际执行，不能提前视为通过 |
| macOS | 尚未验证，不声明完整兼容 |
| Codex CLI | 既有真实调用记录基于 `0.163.0-alpha.10.2`；此次普通 CI 使用模拟接口，不调用账户模型 |
| 外部模型 API | 使用兼容接口模拟测试；各供应商需自行配置并执行连接测试 |

CI 配置见 [.github/workflows/ci.yml](../.github/workflows/ci.yml)，采用只读仓库权限；执行依赖检查、单元与本地 HTTP 测试、JavaScript 语法检查、文档链接检查以及离线示例生成。不要求模型密钥，不将公开服务的临时限流作为普通 CI 的依赖。

手工联网检查使用 `python scripts/check_live.py`，只发送公开测试关键词，不调用模型。真实模型测试是单独的可选步骤，详见 [README](../README.md)。

本轮还通过浏览器执行了教程的离线问答：取消 AI 解释后，成功显示 3 个来自原创笔记的证据片段，材料笔记明确区分预测稳定与实验合成。Excel 相对资料卡链接和 3 条期刊 IF 数值由测试检查；许可入口返回完整 AGPL 文本。本轮没有重新调用真实模型，历史模型实测与本次离线示例分别标注。
