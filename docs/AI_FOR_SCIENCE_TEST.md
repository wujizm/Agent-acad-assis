# AI for Science：自适应筛选验收记录

测试日期：2026-10-17（北京时间）。本地应用：<http://127.0.0.1:8765/>，主题 ID：1。

## 范围与方法

主题名称为 **AI for Science**；检索词为 `artificial intelligence scientific discovery`，范围是 AI 赋能科学发现。
最初直接检索 `AI for Science`，观察到审稿意见、作者回复、AI 教育、科幻和无关书籍等噪声。因此改用更明确的关键词，未把搜索接口返回的数百万条模糊命中数作为领域热度。

真实连接 Crossref 和 Open Library。Crossref 取全时段相关性前 100 条与 2024-01-01 至测试当天的前 100 条；去重后筛选。未配置 OpenAlex、网站搜索或模型服务，界面分别提示缺失配置。

这是一项功能与样本检查，不是穷尽文献检索或学术质量评估。数据源结果、引用数和相关性排序可能变化；原始响应元数据与每次筛选决定保存在主题 `searches/` 中。

## 最终实测结果

| 检查项 | 结果 |
|---|---|
| 近三日历年相关研究候选 | 41 条，自动进入“较多”档 |
| Crossref 去重候选 | 144 条，入选 10 条 |
| Open Library 候选 | 18 条，入选 2 条 |
| 本次有效入选 | 12 条：8 篇论文/会议论文、2 个书籍章节、2 本书籍目录 |
| 具备摘要的有效资料 | 5 条；其余为书目信息，不能支持具体研究结论 |
| 测试库总归档 | 16 条；首次测试中本次未入选的 4 条已标记排除，可在详情恢复 |
| Excel | 17 行（含表头）、25 列；引用来源、时间、入选通道、依据均可导出 |
| 独立文件和 ZIP | 所有 Excel 相对链接均能在 ZIP 内找到，历史筛选记录保留 |
| 零引用 | 显示 `0`，不误显示“未提供” |
| 知识库原文检索 | `scientific discovery lab automation` 返回 7 个原文片段，未返回排除条目 |
| 模型生成 | 未配置，未进行真实模型综述/问答质量验收；模拟接口测试已覆盖 |

自动筛选采用本来源年均引用估值的 P75 与最低值 2 取较高者；本次门槛为 2。年均估值是 `引用次数 / (2026 - 发表年 + 1)`，仅用于排序，不是期刊影响因子，也不代表研究质量。

对**同一份已保存候选**应用不同模式，收录上限均为每来源 10 条（下表比较 Crossref）：

| 策略 | 入选数 | 入选论文平均年均引用估值 |
|---|---:|---:|
| 自动（候选集热度较多） | 10 | 13.66 |
| 广泛收集 | 10 | 6.78 |
| 优先高关注度 | 10 | 13.66 |

平均值仅用于验证筛选确实偏向较高关注度，不能解释为质量提高了相同比例。书籍和章节不纳入此平均值。

## 检查后修正的问题

1. **把搜索结果当作已筛选资料**：增加题名/摘要匹配，作者和期刊名称不参与相关性得分；自动暂缓评审记录、期刊目录、附件和显式撤回/更正通知。撤稿识别仍需人工补查。
2. **引用数为 0 与缺失混淆**：指标作为完整对象保存来源、数值、时间；修正 Excel 文本转换。跨来源合并不会把旧引用数与新来源拼接。
3. **同一章节不同 DOI 占用两个名额**：同题名、同年份、同类型的可能版本只占一个本次入选名额；原始记录不被强行合并，未选版本仍留在审计记录中。
4. **近期通道只偏重题名匹配**：相关性达标后，近期候选优先参考引用情况，避免只有题名特别匹配的零引用条目挤掉更受关注的新工作。零引用/缺失引用的新论文仍可从近期名额入选，回归测试覆盖这一情况。
5. **标题残留标记**：清理 Crossref 题名中的 HTML 标记，同时保留原始元数据。

初次测试的 4 条旧记录仅为此次结果复核而标记排除；不是对其真实性、撤稿状态或质量作判定。应用的日常重复搜集仍保留已有资料和人工核验/排除决定。

## 抽查示例

已核对本地记录与对应来源响应中的题名、作者、年份、DOI 和引用指标；以下仍保留“待人工核验”状态，不表示全文审查或论文结论验证已完成。

- *AI, agentic models and lab automation for scientific discovery — the beginning of scAInce*，Thomas Hartung，2025，Crossref 引用 45；[DOI](https://doi.org/10.3389/frai.2025.1649155)。入选高关注度通道，有摘要。
- *Towards Scientific Discovery with Generative AI: Progress, Opportunities, and Challenges*，Chandan K Reddy、Parshin Shojaee，2025，引用 29；[DOI](https://doi.org/10.1609/aaai.v39i27.35084)。入选高关注度通道，有摘要。
- *Artificial intelligence and scientific discovery: a model of prioritized search*，Ajay Agrawal、John McHale、Alexander Oettl，2024，引用 88；[DOI](https://doi.org/10.1016/j.respol.2024.104989)。入选高关注度通道；本次只取得书目，未推断其研究结论。
- *Artificial Intelligence for Scientific Discoveries*，Raban Iten，2023；[Open Library 目录](https://openlibrary.org/works/OL34336498W)。书籍按相关性收录，不使用论文引用门槛。

本次样本偏向生物医药及一般科学发现，尚不足以覆盖 AI for Science 的材料、物理、化学、气候等全部支线。用于正式材料学综述时，应建立更具体的子主题并补充全文。

## 验证与复查入口

```powershell
python -m unittest discover -s tests -v
node --check static/app.js
```

自动化测试覆盖热度分档、去重、引用门槛、不同策略、低引用新论文保留、缺失指标、初始资料保护、版本名额、Excel/ZIP 与本地 HTTP 等；共 38 项。

实际输出位于 `data/topics/1/`：

- `资料目录.xlsx`：全部归档记录，P 列区分是否纳入。
- `AI-for-Science.zip`：Excel、独立笔记、记录、筛选审计和测试结果。
- `last_search.json` 与 `searches/`：最新条件及各次候选决策。
- `test_results.json`：本次导出、检索与策略比较结果（含入选标题）。
- `test_review.json`：12 条保留 ID 与 4 条旧测试记录排除说明。

指标来源定义参考 [Crossref 元数据格式](https://github.com/CrossRef/rest-api-doc/blob/master/api_format.md)；`is-referenced-by-count` 是 Crossref 收录的入站引用数，不是 JCR 期刊影响因子。
