# Acemap 搜索增强（先导项目）

一个基于 Streamlit 的学术搜索原型，利用规则化意图理解与 GAKG 知识图谱的一跳扩展来增强论文召回，并在客户端完成引用数/发表时间排序优化。

## 功能概览
- 意图解析：通过正则与关键词规则识别排序与实体类型意图，自动清洗核心关键词。
- 图谱召回：在 GAKG 子集上查找 1-hop 相关概念，扩展搜索词，合并去重。
- 客户端排序：针对引用数、发表时间在本地重排 API 候选集，缓解接口排序缺失问题。
- 多类型聚合：同时搜索论文、作者、机构，并以标签页展示。
- 轻量前端：Streamlit 单页界面，支持排序选项与结果提示。

## 目录说明
- [app.py](app.py)：Streamlit 前端与交互逻辑，包含排序映射、结果渲染与页面布局。
- [intent.py](intent.py)：`IntentParser` 规则解析器，提取关键词并识别时间/引用排序及作者/机构类型意图。
- [recall.py](recall.py)：`KGManager` 加载 GAKG 子集，基于 1-hop 邻居扩展概念；`search_with_recall` 合并扩展搜索结果。
- [search.py](search.py)：Acemap API 客户端，提供 `search_acemap`、`search_all` 以及本地排序与 CLI 演示。
- [data/gakg_subset.parquet](data/gakg_subset.parquet)：GAKG 三元组子集数据（subject, relation, object, paperid）。
- [requirements.txt](requirements.txt)：项目依赖。
- [report.md](report.md)：原始项目报告（本 README 摘要来源）。

## 快速开始
1) 安装依赖
```bash
pip install -r requirements.txt
```

2) 启动应用
```bash
streamlit run app.py
```

3) 在浏览器输入关键词（如 "rock"），根据需要选择排序方式。输入包含“recent/most cited”等词会自动推断排序。

## 工作流简述
1) `IntentParser` 清洗查询并给出排序/类型意图。
2) `search_all` 进行作者/机构/论文的基础检索；论文部分可带排序参数触发客户端重排。
3) `search_with_recall` 使用 KG 1-hop 邻居扩展搜索词，合并去重后返回增强论文列表。
4) `app.py` 将增强论文结果覆盖到工作集，按 UI 选择的排序在本地重排并渲染。

## 关键参数与默认值
- 聚合论文数量：基础检索默认 5 条；客户端排序时后台抓取 200–500 条做重排。
- KG 扩展：默认取相关概念 Top-3，每个概念取前 2 条论文（可在 recall.py 中调整）。
- 排序映射：UI 选项映射为 `cited_by_count` 或 `publication_date`，默认降序。

## 已知限制
- 排序在客户端完成，受限于抓取的前 200–500 条候选，无法覆盖全库绝对排序。
- KG 查询基于简单字符串匹配，未做复杂实体对齐；大规模数据时可能需要索引/向量化。
- 依赖公开 Acemap API，接口速率与可用性需关注。

## 开发/调试小贴士
- 首次加载 KG 时使用 `st.cache_resource` 缓存，避免重复读 parquet。
- CLI 体验：`python search.py rock --type work --size 5` 可快速验证搜索接口。
- 如需扩展排序逻辑，可在 `search.py` 的客户端重排部分添加新 key 及比较规则。
