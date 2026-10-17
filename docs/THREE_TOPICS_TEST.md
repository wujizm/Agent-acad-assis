# 三主题完整测试记录

测试日期：2026-10-17（北京时间）。本机 Codex 后端；本地页面 http://127.0.0.1:8765/ 。模型 API 接入方式继续保留。

## 结果

三个主题均完成联网搜集、逐条 AI 整理、重要度排序、文献综述、方向总结、带证据问答及 Excel/ZIP 导出。以下是复核后的纳入数量，不是历史归档总数。

| 主题 | 纳入资料 | 有摘要/节选/正文，可用于综述 | 已核实 IF 的资料 | 最近候选集活跃度 | 归档总数（含排除） |
| --- | ---: | ---: | ---: | --- | ---: |
| AI for Science | 16 | 10 | 6 / 11 篇期刊论文 | 较多：55 条 | 65 |
| 机器学习势函数 | 16 | 10 | 7 / 12 篇期刊论文 | 较多：62 条 | 29 |
| 金属导电理论 | 15 | 7 | 2 / 9 篇期刊论文 | 中等：19 条 | 43 |

热度仅统计 2024–2026 年的相关候选，受查询方式、来源和采样上限影响。机器学习势函数虽专业性强，近期论文仍很活跃，因此没有人为将其设为“低热度”。

综述正文约 1760、2026、2130 个中文字，方向总结约 864、1018、926 个中文字（含标题及覆盖提示，未含参考目录）。问答每次使用 8 个原文片段。只有书目的记录保留在目录中，不用于生成研究结论。

## 自动发现与复核补充

| 主题 | 最近一轮候选：Crossref / Open Library | 最近一轮自动入选 | 最终保留的自动发现资料（含前轮） | 人工指定的新来源 |
| --- | ---: | ---: | ---: | ---: |
| AI for Science | 152 / 50 | 15 | 16 | 0 |
| 机器学习势函数 | 167 / 50 | 12 | 14 | 2 |
| 金属导电理论 | 194 / 50 | 24 | 12 | 3 |

AI for Science：自动找到了 Nature 2023 年综合综述、符号回归综述、fPINNs、Science 的科研 AI 文章及基础书目。复核去掉一本偏土木工程应用的书，保留前轮自动找到的两篇相关综述。对已自动发现的 Nature 综述，从作者 Stanford 页面补充公开 PDF；这属于人工补充文本，不计为新发现来源。

机器学习势函数：自动找到 GAP、矩张量势、神经网络势综述、势函数验证、不确定性量化、通用势系统性软化及声子基准等资料。最近一轮书籍候选没有达到主题相关性要求，未强行填满；保留前轮发现的 GAP 书目。另补充 2025 年 Nature Computational Science 综述的公开摘要，以及 NIST 原子势项目页面。不能把这两条算作自动搜索能力的成果。

金属导电理论：自动找到 Greenwood 1958 年关于 Boltzmann 方程与金属导电的文章，以及 Kittel、Olsen、Phillips 等书目。自动结果也混入了偏纳米线器件工艺的论文，复核排除 4 条应用性过强的记录，并精简重复的基础书目。另指定补充 Tong 的公开教材章节、Planckian 耗散综述和 Kubo 1957 年经典论文元数据。

这次测试说明：英文同义词扩展与语义筛选有助于发现专业主题资料，但自动结果仍需相关性复核。没有人工建立的完整标准文献集，不能据此报告召回率。专业讲义、经典论文及出版版本仍存在漏检。

## 检索式

| 主题 | 论文检索式 | 书籍检索式 |
| --- | --- | --- |
| AI for Science | AI for Science；artificial intelligence scientific discovery；Bayesian experimental design；physics informed neural networks；symbolic regression | scientific computing；probabilistic machine learning |
| 机器学习势函数 | machine learning interatomic potentials；machine learned potentials；potential energy surface；Gaussian approximation potentials；neural network potentials | Atomistic Simulation；Molecular Dynamics |
| 金属导电理论 | electrical conduction in metals；metallic electrical conductivity；Drude model；Sommerfeld free electron theory；Boltzmann transport theory | solid state physics；electronic transport in metals |

Crossref 采用 `query.title`。实测通用书目字段检索曾遗漏核心综述，并引入不相关结果；题名检索改善了这次候选集合。候选仍是有限采样，不是系统综述的穷尽检索。

## IF 与重要度

当前指标目录覆盖 34 本期刊，保存公开核实的 **2025 JIF**、出版社 URL 和核实日期。不是完整 JCR 数据库，也没有将 CiteScore 或论文引用数冒充 IF。

样例：Nature 56.1、Science 47.3、Artificial Intelligence Review 18.8、npj Computational Materials 13.1、Journal of Chemical Physics 3.7、Physical Review Letters 9.4、Reviews of Modern Physics 48.9。分别依据 [Nature 指标页](https://www.nature.com/nature-portfolio/about-journals/journal-metrics)、[Science 指标页](https://www.science.org/content/page/journal-metrics-overview)、[Springer 期刊页](https://link.springer.com/journal/10462)、[AIP 期刊说明](https://pubs.aip.org/aip/jcp/pages/about)与 [APS 指标页](https://journals.aps.org/metrics)。

重要度权重：相关性 60、同来源论文关注度 20、IF 10、文本覆盖 5、时效 5。缺失/不适用项不记为零，剩余权重重新归一。相关性语义判断以搜集时的题名/摘要为依据，界面显示其理由；不是全文质量评审。书籍与讲义不适用 IF，仍可有较高阅读优先级。

Excel 的排名、重要度、IF、IF 年份均为数值单元格，支持排序；缺失项明确标记。表内包含 IF 官方来源超链接。默认按纳入状态及重要度导出，排除记录保留在末尾且没有排名。GUI 可切换重要度、发表时间或已核实 IF 排序。

## 检查与修正

1. GUI 改为 #003366 主色，搭配浅蓝背景、蓝灰文字及低饱和金色提示，保留原有操作流程。
2. 增加中文主题的英文同义词/分支检索；将论文与书籍检索式分开，防止长检索词导致书籍检索失效。
3. 结合语义相关性、引用指标、已核实 IF 与近期/经典/基础资料名额筛选；高 IF 不使无关资料通过相关性门槛。理论类主题的判断提示进一步强调物理机制，避免仅凭应用论文含有相同词项就入选；这不能代替人工复核。
4. 长篇资料由“仅取开头”改为“保留开头并检索主题相关正文”。发现参考文献列表因关键词密集而被高排位检索后，增加编号及年份密度判断，跳过以参考文献为主的片段，同时保留含实质正文与少量末尾引文的混合片段。原文与片段编号不改写；启发式不能识别所有版式。
5. 关联出版版本使用预印本文本时，向整理、报告和问答传递版本说明。Planckian 综述采用 arXiv:2107.07802v3，已明确未与出版版本逐段比对。
6. Excel 的紧凑指标列居中显示，避免 IF 年份、状态和相邻数值连在一起。

验证结果：54 项自动化测试通过，JavaScript 语法检查通过；三主题全部整理结果与报告均未过期。引用编号均能定位到当前纳入的原文片段，本次报告及问答未引用纯参考文献片段。逐段阅读六份报告和三次问答，抽查其数字、方法限制及摘要/正文区分；未发现需要进一步修正的明确证据错配，但不等于完成全面学术核验。

三个 Excel 已用独立工作簿读取器及渲染器检查。核对了数值类型、IF 年份与来源、排名连续性、缺失值、逐条笔记链接、原件及 ZIP 完整性。资料包中的每条归档记录均有独立 Markdown 与 JSON。

最终重启服务后，浏览器实测了主题切换、IF 排序、资料详情中的官方指标链接及已有综述阅读；通过 GUI 提问“Drude 与 Lindhard 模型有什么联系？已有资料是否给出了适用条件？”，成功返回带可点击引用的回答，并明确摘要未给出完整适用条件。三个 Excel 和六个报告的 HTTP 下载链接均成功，服务错误日志为空。界面截图见 [three-topics-preview.png](three-topics-preview.png)。

## 已知边界

- 本机未配置 OpenAlex 与可信网站搜索所需凭据；此次自动搜索使用 Crossref 和 Open Library。公开讲义与 NIST 页面通过指定 URL 补充。原有可选接入功能仍在。
- 全文获取受公开可读性限制；机器学习势函数的期刊材料主要为摘要。Kubo 经典文章仍只有元数据，不据此补造理论推导。
- IF 只覆盖已核实期刊；2025 IF 不代表某篇老论文发表当年的 IF，更不代表单篇质量。
- 广义 AI for Science 的本次证据偏向符号回归与物理信息网络，未覆盖所有学科路线。机器学习势函数的静态验证不能直接推广到所有动力学模拟；金属输运中也不能把 Planckian 时间当作所有材料的严格普适下界。
- 数据库保留测试前及复核排除记录，网页“已归档资料”会多于表格中的最终纳入数量。

## 文件与复跑

- 三个主题的原始资料包、Excel 和报告保存在作者本机 `data/topics/`，不随源码发布。在自己的资料库运行后，可通过网页下载对应主题成果；主题编号由本机数据库决定。
- 可公开复现的输入与步骤见 [AI for Science 标准教程](../examples/ai-for-science/README.md)，包含离线示例、联网搜集、生成报告及验证方法。它与本次历史真实模型测试的数据集不同。
- [结构化核查结果](three-topics-validation.json)

每个主题目录还含 `last_search.json`、`searches/`、`validation-curation.json` 及带回答和证据的 `validation-finish.json`。人工复核操作与自动候选分别记录。

```powershell
python -m unittest discover -s tests -v
node --check static/app.js
# 下列操作会联网并使用已配置模型的额度；collect 会新增/合并归档记录。
python scripts/run_topic_validation.py collect --topic 'AI for Science' --limit 15
# 核查候选、排除无关资料并补充公开原文后，生成完整成果。
python scripts/run_topic_validation.py finish --topic 'AI for Science'
```

另两个主题可将 `--topic` 替换为对应中文名称。`finish` 会重新排序、跳过未改变的单篇整理，并重生成报告、问答与导出；不会自动复现人工补充来源及排除决定。
