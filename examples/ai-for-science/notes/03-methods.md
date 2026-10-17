# AI for Science 教学笔记：跨领域案例与方法基础

> 项目原创教学说明，采用 AGPL-3.0-only。用于演示知识脉络和问答，不是书籍章节、论文原文或最新进展清单。

Jumper 等的 AlphaFold 论文是蛋白质结构预测的代表性工作。学习这个案例时，可以关注科学知识怎样进入模型设计，以及评测任务能支持什么范围的结论。它在特定任务上的表现不能直接证明同类方法能解决全部科学问题。

把蛋白质结构预测与晶体候选发现放在一起，可以比较问题定义、结构表征、训练数据和验证标准。这是一个跨领域学习框架，而不是把两个领域的评价指标直接混为一谈。

Murphy 的《Probabilistic Machine Learning: An Introduction》可作为方法学习的书目入口。本示例没有取得或导入该书章节，因此不能引用这条书目来证明某个公式、算法推导或具体页码。

建议的学习顺序为：概率与统计基础 → 监督学习与模型评估 → 领域结构表征 → 不确定性与分布外验证 → 科学任务中的候选筛选及验证。这个顺序由本教程提出，读者应根据自己的材料学课题调整。

阅读入口：[Jumper 等，Highly accurate protein structure prediction with AlphaFold，Nature，2021](https://doi.org/10.1038/s41586-021-03819-2)；[Murphy 的书籍主页](https://probml.github.io/pml-book/book1.html)。
