# 许可与第三方依赖

本项目原创代码、原创教程和原创教学笔记采用 **AGPL-3.0-only**。Copyright (C) 2026 知材项目贡献者。完整条款见 [LICENSE](LICENSE)，软件按原样提供，不提供担保。许可证全文取自 GNU AGPL v3，由 [GitHub Choose a License](https://choosealicense.com/licenses/agpl-3.0/) 提供的标准副本保存，未改写条款。

允许在遵守条款的前提下使用、修改和分发。分发修改版时应保留声明、标注修改并按条款提供相应源码；将修改版用于面向用户的网络服务时，应履行 AGPL 第 13 条的源码提供义务。本项目的源码发行包包含启动、依赖和构建/测试说明。依赖库的许可证不会被本项目的声明替换。

## Python 依赖

下表对应 [constraints-tested.txt](constraints-tested.txt) 的依赖快照。完整原有声明的副本保存在 [licenses/third-party](licenses/third-party)。升级依赖后应重新核对版本、许可及对应的声明文件。

| 组件 | 版本 | 许可 | 用途 / 上游 |
| --- | --- | --- | --- |
| PyMuPDF / MuPDF | PyMuPDF 1.28.2 | AGPL-3.0 或 Artifex 商业许可；本项目使用 AGPL 路线 | PDF 文字提取；[上游许可](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) |
| requests | 2.34.2 | Apache-2.0 | 模型 API / URL 编码；[项目](https://github.com/psf/requests) |
| urllib3 | 2.8.0 | MIT | 绑定已验证地址的资料抓取；[项目](https://github.com/urllib3/urllib3) |
| openpyxl | 3.1.5 | MIT | Excel 导出；[项目](https://pypi.org/project/openpyxl/) |
| certifi | 2026.7.22 | MPL-2.0 | CA 证书包；[项目](https://github.com/certifi/python-certifi) |
| charset-normalizer | 3.5.2 | MIT | requests 的字符编码依赖；[项目](https://github.com/jawah/charset_normalizer) |
| idna | 3.20 | BSD-3-Clause | 国际化域名；[项目](https://github.com/kjd/idna) |
| et-xmlfile | 2.0.0 | MIT；另附所含代码的原有 Python 许可声明 | openpyxl 的 XML 写入依赖；[项目](https://pypi.org/project/et-xmlfile/) |

本仓库不打包 Python、Codex CLI、上述第三方二进制包或 MuPDF 的内嵌组件。依赖通过包管理器从上游安装，其内嵌组件保留各自许可；若另行制作包含这些组件的安装包，应同时满足对应源码和声明要求。

## 文献、指标与示例内容

- 引用的论文、书籍及网页仍归原权利人所有，本项目的 AGPL 声明不覆盖这些作品。
- `examples/ai-for-science` 只包含公开书目事实、来源网址及项目原创教学材料，不分发论文 PDF、整篇摘要、整本书或个人资料库。自己的教学解释与论文原文分别记录。
- `resources/journal_metrics.json` 是少量出版社公开指标的核实快照，附指标年份、来源和日期；不是完整 JCR 数据库，也不授予对第三方数据库的再分发权。
- 用户自行导入的资料、密钥、登录信息及生成的个人资料库不属于源码发布内容。
