# 上市公司事件追踪与核验助手

研究人员可以批量导入中文合同材料，查看程序抽取的公司、项目、动作、金额和引句，并按信息披露时间回看。当前使用本地规则与 SQLite。跨材料事件归并和可信评估在开发计划中。

## 直接看成果

下载后双击 [八份虚构材料的证据预览](out/11月26日-事件证据预览.html)，点击“查看材料全文”对照引句。[历史截面](out/11月4日-历史截面.html) 只展示 11 月 4 日 15 时之前已披露的材料。两个页面都是可离线打开的导出结果。

## 自己运行

在项目根目录打开终端。需要 Python 3.10 或以上，仅使用标准库。依次执行以下命令。

```powershell
python -m src.event_tracker import data/examples/D1-D5.json
python -m src.event_tracker import data/examples/D6-D8.json
python -m src.event_tracker show --html out/我的预览.html --json data/processed/抽取结果.json
python -m src.event_tracker show --until "2026-11-04 15:00" --html out/我的历史截面.html
python eval/run_eval.py
```

首次导入分别新增 5 和 3 份材料，再运行计为重复。打开 out/我的预览.html 查看新结果。自己的材料按示例填写“编号、发布时间、来源、正文”。同编号内容发生变化会提示冲突并保留原文，单项失败可修正后重新导入。

## 文件放在哪里

- `docs/` 按 01—06 阅读题目解读、产品定义、分类、核验口径、评测设计和实施方案。`docs/答辩/` 存放答辩资料。
- `data/raw/` 本地原始材料，按企业样例、公告、新闻等存放，按只读约定使用。`data/examples/` 是可随仓库分发的虚构输入，不含参考答案。
- `data/interim/` 是可由输入重建的 SQLite 工作库。`data/processed/` 是结构化抽取结果。`data/groundtruth/` 放逐条人工标注，手工维护。
- `src/ingest/` 导入、去重，`src/extract/` 合同抽取，`src/common/` 存储和时间处理。`src/link/`、`src/verify/` 预留给归并、核验。`app/` 生成预览。
- `eval/cases/` 只放题目，`eval/expected/` 放按题号关联的答案。`eval/reports/` 保存每次运行报告。当前 5 项自动检查为开发回归，独立评测尚待开展。
- `out/` 保存页面和展示产物。`notebooks/` 放探索性试验。`archive/` 保存历史资料。

Git 跟踪公开虚构输入、代码、文档、虚构样例快照与回归记录。原始材料、人工标注、数据库、一般导出、本地聊天归档与环境密钥默认忽略。
