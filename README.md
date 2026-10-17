# 知材 · 材料学科研资料整理 Agent

面向个人使用的本地网页应用：按主题搜集论文、书籍及其他资料，导出 Excel 与独立资料文件，生成主题综述和科研方向总结，并通过原文检索进行带引用的问答。

**第一次使用：**从 [AI for Science 标准示例教程](examples/ai-for-science/README.md) 开始。无需模型即可建立独立示例库、查看资料、检索证据和导出 Excel；教程也包含联网搜集和真实模型生成的完整步骤。

项目采用 **AGPL-3.0-only**，见 [LICENSE](LICENSE) 和 [第三方依赖声明](THIRD_PARTY_NOTICES.md)。发布范围、网络修复和兼容性说明见 [发布准备说明](docs/RELEASE_PREPARATION.md)。

实施计划及检查结果见 [docs/PLAN.md](docs/PLAN.md)。

2026-10-17 的 GUI、IF 排序及三主题完整测试见 [docs/THREE_TOPICS_TEST.md](docs/THREE_TOPICS_TEST.md)，包含自动发现与人工补充的区分、资料包及检索边界。

## 启动

需要 Python 3.11 或更高版本。本机已验证 Windows / Python 3.13.7；其他环境的验证范围见发布准备说明。在项目目录中运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -c constraints-tested.txt
.\.venv\Scripts\python.exe run.py
```

浏览器打开 <http://127.0.0.1:8765>。也可在依赖安装完成后运行 `start.ps1`，或直接 `python run.py`。不必激活虚拟环境，不需要全局安装包。

可选择端口与数据目录：

```powershell
python run.py --port 8766 --data-dir .test-output/demo
```

服务只监听本机；关闭启动终端或按 Ctrl+C 停止服务。应用不适合直接暴露到公网。

## 配置模型和可选搜索服务

网页左下角的 **模型与搜集设置** 可切换“本机 Codex”与“模型 API”，并执行一次真实连接测试。切换立即生效；任务运行期间禁止切换。原有 API 地址、模型和密钥保留在 `.env` 中。

### 本机 Codex（适合当前本机调试）

使用已安装的官方原生 Codex CLI，在本机终端完成登录：

```powershell
codex --version
codex login
codex login status
```

已有有效登录时无需再次登录。在网页设置中选择“本机 Codex”，点击“保存并测试连接”，之后直接使用 AI 整理、综述、方向总结和问答。无需在本项目填写 OpenAI API Key；通过 ChatGPT 登录时使用该账户的 Codex 额度，CLI 若以 API Key 登录则按对应 API 方式计费。

默认从 PATH 查找原生 `codex` 可执行文件。若未找到，可在 `.env` 设置 `CODEX_COMMAND=C:/完整路径/codex.exe` 并重启。Windows 不接受 `.cmd`、`.bat`、`.ps1` 包装脚本。适配器要求 CLI 支持 `--ignore-user-config`、`--ephemeral`、`--output-schema`；旧版本不支持时需更新官方 CLI。

Codex 模型可留空使用 CLI 内置默认值，也可填写账户可用的模型名称。为避免带入写代码时的插件和工具配置，本次调用不加载用户 `config.toml`，所以不会继承其中的默认模型、自定义代理或认证存储选项；登录仍由官方 CLI 管理。遇到认证差异请先检查 CLI 登录与存储配置，不要复制或导出登录凭据。

调用通过 UTF-8 标准输入发送文本，使用临时工作目录、只读沙箱、关闭命令执行/浏览器/插件等工具，只读取结构化最终答案。单次调用超时为 5 分钟，失败时保留原资料；不会自动切换到其他模型服务。`--ephemeral` 不保留会话文件，但官方 CLI 自身仍可能写运行日志，应用不会把 CLI 原始日志展示在网页中。

接入方式与 Codex 模型保存在 `data/model-settings.json`，优先于 `.env` 的 `LLM_BACKEND` / `CODEX_MODEL`，重启后保留。此文件只存非敏感选择，不包含密钥。

### 模型 API（保留原有功能）

1. 将 `.env.example` 复制为 `.env`（仅首次创建，勿覆盖已有配置）。
2. 使用本地文本编辑器填入服务地址、模型和密钥。
3. 重启应用。不要把密钥提交到 Git 或发送到聊天中。

```dotenv
LLM_BASE_URL=https://你的服务地址/v1
LLM_MODEL=你已开通的模型名称
LLM_API_KEY=你自己的密钥
```

接口采用 `POST {LLM_BASE_URL}/chat/completions`，输入 `model` 与 `messages`，读取 `choices[0].message.content`。模型需能遵循 JSON 与引用格式要求。可用任意兼容的远程服务，或例如 `http://127.0.0.1:11434/v1` 的本地兼容服务；本地服务若无需密钥可留空。不要把 `/chat/completions` 再填进根地址。

| 配置 | 用途 | 是否必需 |
|---|---|---|
| `LLM_BACKEND` | 初始接入方式：`api`（默认）或 `codex`；网页保存的选择优先 | 可选 |
| `CODEX_COMMAND`、`CODEX_MODEL` | Codex 原生程序路径、可选模型名 | 可选，默认从 PATH 查找程序 |
| `LLM_BASE_URL`、`LLM_MODEL` | 模型 API 服务地址与模型名 | API 模式需要 |
| `LLM_API_KEY` | 模型服务鉴权 | 按服务要求 |
| `OPENALEX_API_KEY` | 增加摘要、作者与单位等元数据来源 | 可选 |
| `BRAVE_SEARCH_API_KEY` | 在主题指定域名中检索可信网页 | 可选 |
| `CONTACT_EMAIL` | 向公共元数据服务标识联系信息 | 可选 |

**无模型配置仍可搜集、导入、编辑、导出和检索原文。** 不会伪装生成 AI 综述。资料在本机保存，但点击 AI 功能后，相关片段会发送到你配置的模型服务；本地存储不等于本地推理。密钥不进入资料文件、Excel 或 API 状态响应。

## 使用流程

1. **创建主题**：中文名称方便管理，检索词建议使用该领域常用的英文表达。需要网页自动搜索时填写机构/出版社等域名列表。
2. **联网搜集**：每个来源最多收录 1–25 条，默认 10 条。默认按主题候选集热度调整筛选；也可选择“广泛收集”或“优先高关注度”。Crossref 搜索 DOI 注册资料，Open Library 搜索书籍目录；配置后增加 OpenAlex 和可信网站搜索。结果应检查相关性，不代表穷尽检索。
3. **补充原文**：导入公开网址、PDF、UTF-8 TXT 或 Markdown，也可手工粘贴摘要/章节。已收录资料可在详情中“抓取原文”。扫描 PDF 需先 OCR。
4. **校对资料**：编辑作者单位、来源、年份与题名；无关或错误资料勾选“排除”。已核对原文的资料可标记“已人工核验”。
5. **AI 整理资料**：生成中文/英文译名、一句话简介和主要内容。保留原题名，绝不让模型填补作者单位。单篇使用文本前 16000 字符，卡片明确记录覆盖长度；长书建议按章节导入。
6. **导出**：Excel 为总目录；建议下载整个主题 ZIP，解压后 Excel 中的相对链接能打开对应 Markdown 文件。单独下载 Excel 时，其文件链接需要配套的 `sources/` 目录。
7. **综述与方向**：分别生成主题文献综述和科研方向总结，附参考资料和证据覆盖清单。更新任何资料后，已有报告显示“需重新生成”。
8. **知识库问答**：只检索当前主题中未排除的原始文本。每个引用可打开原资料，并展示实际检索片段。未配置模型时返回片段列表。

## 输出结构与字段

```text
data/
  library.sqlite3              # 唯一结构化数据源
  topics/<主题编号>/
    资料目录.xlsx
    topic.json
    last_search.json           # 最近一次搜集条件、成功/失败和覆盖说明
    searches/<时间>-<编号>.json # 每次候选、引用指标、入选/暂缓理由，保留历史
    sources/S....md            # 每条资料一个 Markdown 文件
    records/S....json          # 资料元数据、来源记录及提取文本
    originals/                 # 上传原件或从网址取得的原文件快照
    reports/review.md
    reports/direction.md
```

Excel 包含：原题名、中英文题名、来源（期刊/出版社/机构）、作者、作者主要单位、简介、类型、年份、DOI、ISBN、网址、内容覆盖范围、核验状态、是否纳入、独立文件链接、获取日期及备注，以及引用次数、引用来源/时间、候选集热度、入选通道和依据、重要度排名/分数、期刊 IF/指标年份/核实状态/官方来源/核实日期。来源无法提供的字段显示“未提供”；引用次数为 0 和缺失分开记录。“作者主要单位”保留来源给出的作者—单位对应关系，不凭作者当前主页或出版社名称猜测。

数据库为权威数据源。请在网页内修改后重新导出；直接编辑 Excel 或生成的 Markdown 不会反向同步，重新导出会覆盖生成文件。原始上传文件按独立名称保留。

## 按主题热度筛选

- **检索扩展**：已连接模型时，自动将中文主题扩展为 4–5 组互补英文论文检索式，并生成 1–2 组书籍检索式。手工用分号分隔多组检索词时按原设置执行。Crossref 使用题名检索，避免其他书目字段的词项把核心文献挤出候选。论文来源的全时段和近三日历年样本各最多 100 条，多组检索均分配额；书籍最多 50 条，可信网站最多 20 条。
- **相关性与热度**：已连接模型时，对候选题名/摘要分批进行语义相关性判断，记录分数及理由；失败或未配置时回退到词项匹配。判断不是内容核验。热度只数近期相关论文、预印本和报告：≥40 条较多、15–39 条中等、1–14 条较少，无有效样本为数据不足。它是候选集活跃度代理，不是全领域发文量。
- **自动门槛**：较多/中等时，以同来源年均引用第 75/50 百分位（至少 2/1）或已核实 IF≥10/5 进入核心候选，按重要度选取。保留 30% 近期研究、最多 10% 经典文献和 20% 基础资料名额；其余名额优先核心候选，不强行填满。小众方向按相关性收录；书籍与网站不套用论文引用门槛。
- **IF 与阅读重要度**：`resources/journal_metrics.json` 为人工核实的出版社公开指标快照，保留 JIF 年份、URL 和核实日期，按精确期刊名/ISSN 匹配。它不是完整 JCR 数据库，也不保证覆盖所有期刊。未核实/不适用不记为 0，当前指标不是文章发表当年的 IF。重要度权重为相关性60、同来源引用关注度20、期刊IF10、文本覆盖5、时效5；缺失指标不计并重分权重。该分数只建议阅读顺序，不是科研质量评分。界面可改按年份或 IF 排序，更新数据后可点击“刷新 IF 与重要度”。
- **可追溯与复核**：网页、Markdown、Excel 显示排名与依据。`searches/` 保存所有候选、相关性判断和入选/暂缓理由，最近一轮可在网页下载。重复搜集不删除旧资料，也不覆盖人工排除/核验标记；对有问题的条目可标记排除。自动排除评审、附件、显式撤稿/更正通知不构成完整撤稿核验。专业综述仍需核查出版版本、补充核心全文。

## 第一版实现与限制

- **协调方式**：明确的工作流调用搜集、存储、阅读与写作工具；不依赖多 Agent 框架。模型只处理文本，不执行任意代码或系统命令。
- **去重**：同一主题按 DOI、ISBN、规范化 URL、上传文件哈希及必要的题名/年份匹配。不同书籍版本不只按书名合并。
- **证据范围**：区分书目、摘要、节选/网页与全文提取文本。书籍目录不能支持书中研究结论。自动抓取可能包含导航或遗漏正文，需检查。
- **综述覆盖**：每次最多 100 条有文本的资料，按阅读重要度排序；总原文预算约 60000 字符，每条最多 4200 字符，保留开头介绍并检索主题相关段落。综述与问答跳过密集编号参考文献片段（编号及年份密度启发式，不能识别所有版式），保留原文与原片段编号。报告列出纳入数、每条使用量及遗漏条目。适合初步资料综述；重要科研判断应补充全文精读。
- **检索方式**：本地 BM25 风格关键词检索，支持中文二元词及英文/化学式；配置模型时先扩展中英文检索词。未启用向量检索，跨语言召回仍可能遗漏。
- **引用检查**：拒绝模型返回未提供的资料/片段编号、数字式虚构引用和模型自行生成的网址。编号有效不等于论断得到证据充分支持，仍需人工核验。
- **内容提取**：目前不做 OCR、表格结构还原或图像理解；不自动获取付费论文/整本书。未开放内容可以导入合法取得的本地文件。
- **网络**：公共服务可能限流或不可达，界面分别列出各来源错误。旧资料始终保留；可稍后重试，不将网络失败当作“无结果”。
- **资料抓取边界**：仅连接已验证的公网 IP，跳转和连接回退同样校验；HTTPS 仍检查原域名证书。不隐式使用环境/系统 HTTP 代理或 `.netrc`。依赖代理的环境需另行适配，或先合法下载后上传；不通过放开内网地址恢复访问。
- **长任务**：同一服务同时运行一个搜集/生成任务；刷新网页不会取消后台线程，但任务提示目前不跨刷新恢复。停止服务会中断未完成任务，已入库资料保留。

## 检查

```powershell
python -m unittest discover -s tests -v
node --check static/app.js
python scripts/check_docs.py
python scripts/check_live.py
```

前三项无需网络或密钥。`check_live.py` 仅以公开的测试关键词读取 Crossref/Open Library，不调用模型、不发送私人资料。[GitHub Actions](.github/workflows/ci.yml) 将在提交和 PR 时运行自动检查及离线示例；Windows/Ubuntu 的 Python 3.11/3.13 结果需以实际 CI 执行为准。

测试覆盖去重、版本区分、作者单位映射、PDF 文字提取与扫描件提示、跨主题隔离、排除条目、原文检索、AI 接口模拟、引用检查、报告失效、Excel/ZIP 链接、公式注入、本地 HTTP 流程，以及热度分档、高关注度筛选、近期零引用保留、候选审计与重复搜集。真实模型的输出质量需要在配置具体服务后评估。

模型测试还覆盖接入方式持久化、API 配置保留、运行中禁止切换、Codex 中文标准输入、最终答案解析、超时及错误日志隔离。网页“保存并测试连接”会调用所选模型，可能消耗该服务额度。

可选真实 Codex 测试（会发送选中资料的文本并使用账户额度）：

```powershell
python scripts/check_codex.py --source-id 资料ID --question "一个基于该资料的问题"
```

脚本在临时资料库副本中进行单篇整理及带引用问答，不修改原资料；结果写入 `.test-output/codex-live/时间/`。本机 AI for Science 实测记录见 [docs/CODEX_TEST.md](docs/CODEX_TEST.md)。

## 接口与设计参考

- [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [Crossref 引用计数字段定义](https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md)
- [Open Library Search API](https://openlibrary.org/dev/docs/api/search)
- [OpenAlex API 认证变更公告](https://groups.google.com/g/openalex-users/c/rI1GIAySpVQ)
- [Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search)
- [Chat Completions API](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [Codex 非交互调用与结构化输出](https://learn.chatgpt.com/docs/non-interactive-mode)
- [Codex 官方登录方式](https://learn.chatgpt.com/docs/auth)
- [PaperQA2 文献检索设计复盘](https://www.futurehouse.org/research/engineering-blog-journey-to-superhuman-performance-on-scientific-tasks)
